#!/usr/bin/env python3
# Distribuído sob a licença MIT. Consulte o arquivo COPYING.
"""Verifica o gênese, os endereços e o isolamento da rede REAL-26."""

import copy
from decimal import Decimal
import hashlib
import os
import sys
from pathlib import Path

from test_framework.blocktools import add_witness_commitment, create_block, create_coinbase
from test_framework.messages import COIN, COutPoint, CTransaction, CTxIn, CTxOut
from test_framework.segwit_addr import encode_segwit_address
from test_framework.test_framework import BitcoinTestFramework, SkipTest
from test_framework.util import append_config, assert_equal, assert_raises, assert_raises_rpc_error, p2p_port


SCRIPT_MINERACAO = bytes.fromhex("5220" + "01" * 32)


VETOR_MLDSA65 = "r26pq1z76su42w8wyu3zu0sxgtze4rfvw388gqph7xefrdsrsek0ats0s0qkn30rt"


class Real26Regtest(BitcoinTestFramework):
    def set_test_params(self):
        self.num_nodes = 3
        self.setup_clean_chain = True
        self.uses_wallet = True
        self.extra_args = [[], [], ["-v2transport=0"]]

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()
        if not self.config["components"].getboolean("REAL26_EXPERIMENTAL_MLDSA65", fallback=False):
            raise SkipTest("A compilação não inclui ML-DSA-65.")
        try:
            import cryptography  # noqa: F401
            import mnemonic  # noqa: F401
        except ImportError as erro:
            raise SkipTest("Instale python3-cryptography e python3-mnemonic para testar a carteira ML-DSA-65.") from erro

    def setup_network(self):
        self.add_nodes(self.num_nodes, self.extra_args)
        for node in self.nodes[:2]:
            # O cookie RPC e os logs seguem o subdiretório de dados da rede.
            node.chain = "real26mldsa-pq"
            append_config(node.datadir_path, ["real26dev=1"])
        self.start_nodes()
        self.connect_nodes(1, 0)

    def run_test(self):
        minerador, par, bitcoin = self.nodes
        genesis = "26df5874074ef2b195f095a7f38d13db0dbf22e11b4ab1b22d881303fc408905"
        assert_equal(minerador.getbestblockhash(), genesis)
        assert_equal(par.getbestblockhash(), genesis)
        assert_equal(bitcoin.getbestblockhash(), "0f9188f13cb7b2c71f2a335e3a4fc328bf5beb436012afca590b1a11466e2206")

        script = "0014" + "01" * 20
        addr = minerador.decodescript(script)["address"]
        assert addr.startswith("r26pq1")
        assert_equal(bitcoin.validateaddress(addr)["isvalid"], False)
        assert_equal(minerador.validateaddress(bitcoin.decodescript(script)["address"])["isvalid"], False)

        descritor = minerador.getdescriptorinfo(f"raw({SCRIPT_MINERACAO.hex()})")["descriptor"]
        blocos = self.generatetodescriptor(
            minerador, 3, descritor, sync_fun=lambda: self.sync_blocks(self.nodes[:2]),
        )
        assert_equal(minerador.getblockcount(), 3)
        assert_equal(par.getblockcount(), 3)
        assert_equal(par.getbestblockhash(), blocos[-1])
        assert_equal(bitcoin.submitblock(minerador.getblock(blocos[0], 0)), "prev-blk-not-found")

        # Força o transporte V1 para verificar diretamente os quatro bytes do cabeçalho P2P.
        with bitcoin.assert_debug_log(["Wrong MessageStart b493d566 received"], timeout=10):
            minerador.addnode(f"127.0.0.1:{p2p_port(2)}", "onetry", v2transport=False)
        assert_equal(bitcoin.getblockcount(), 0)
        self.log.info("Dois nós REAL-26 sincronizados e o nó Bitcoin permaneceu no gênese.")
        assert_equal(minerador.getblocktemplate({"rules": ["segwit"]})["height"], 4)
        [bloco_bitcoin] = self.generatetodescriptor(bitcoin, 1, "raw(51)", sync_fun=self.no_op)
        assert_equal(bitcoin.getblock(bloco_bitcoin, 2)["tx"][0]["vout"][0]["scriptPubKey"]["hex"], "51")
        self.testar_gasto(minerador, par)
        self.testar_carteira_core(minerador, par)

    def testar_gasto(self, minerador, par):
        ambiente = self.config["environment"]
        sys.path.insert(0, ambiente["SRCDIR"])
        from experimentos.mldsa65 import carteira

        binarios = Path(ambiente["BUILDDIR"]) / "bin"
        ferramenta = binarios / ("real26_mldsa65_sign_test" + ambiente["EXEEXT"])
        cli = binarios / ("bitcoin-cli" + ambiente["EXEEXT"])
        arquivo = Path(self.options.tmpdir) / "carteira-real26"
        senha = "senha de teste sem valor real"
        frase = carteira.gerar_frase()
        publica = carteira.criar_carteira(arquivo, senha, ferramenta, frase=frase)

        # Fixa a derivação do endereço, independentemente da senha do arquivo.
        vetor = carteira.lista_frase().to_mnemonic(bytes(32))
        assert_equal(bytes(carteira.decodificar_frase(vetor)), bytes(32))
        publica_vetor = carteira.criar_carteira(arquivo.with_suffix(".vetor"), senha, ferramenta, frase=vetor)
        assert_equal(carteira.endereco(publica_vetor), VETOR_MLDSA65)
        assert_raises(ValueError, carteira.decodificar_frase, " ".join([vetor.split()[0]] * 24))
        assert_raises(ValueError, carteira.decodificar_frase, " ".join(["invalidword"] * 24))
        assert_raises(FileExistsError, carteira.criar_carteira, arquivo, senha, ferramenta)
        assert_raises(ValueError, carteira.abrir_carteira, arquivo, "senha incorreta")
        assert_raises(ValueError, carteira.abrir_publica, arquivo, "senha incorreta", ferramenta)
        assert_equal(carteira.abrir_publica(arquivo, senha, ferramenta), publica)
        sem_frase = arquivo.with_suffix(".sem-frase")
        publica_sem_frase = carteira.criar_carteira(sem_frase, senha, ferramenta)
        assert_equal(carteira.abrir_carteira(sem_frase, senha)[0], publica_sem_frase)
        assert_equal(carteira.abrir_publica(sem_frase, senha, ferramenta), publica_sem_frase)
        if os.name == "posix":
            assert_equal(arquivo.stat().st_mode & 0o777, 0o600)
        dados = arquivo.read_bytes()
        corrompido = arquivo.with_suffix(".adulterada")
        corrompido.write_bytes(dados[:-1] + bytes([dados[-1] ^ 1]))
        assert_raises(ValueError, carteira.abrir_carteira, corrompido, senha)
        assert_raises(ValueError, carteira.abrir_publica, corrompido, senha, ferramenta)

        endereco = carteira.endereco(publica)
        assert endereco.startswith("r26pq1z")
        assert_equal(minerador.validateaddress(endereco)["isvalid"], True)
        script_mldsa65 = b"\x52\x20" + carteira.compromisso(publica)
        def sync():
            return self.sync_blocks(self.nodes[:2])
        descritor = minerador.getdescriptorinfo(f"raw({script_mldsa65.hex()})")["descriptor"]
        bloco_fundos, *_ = self.generatetodescriptor(minerador, 3, descritor, sync_fun=sync)
        descritor = minerador.getdescriptorinfo(f"raw({SCRIPT_MINERACAO.hex()})")["descriptor"]
        self.generatetodescriptor(minerador, 100, descritor, sync_fun=sync)

        coinbase = minerador.getblock(bloco_fundos, 2)["tx"][0]
        valor = 50 * COIN
        tx = CTransaction()
        tx.version = 2
        tx.vin = [CTxIn(COutPoint(int(coinbase["txid"], 16), 0))]
        tx.vout = [CTxOut(valor - 10_000, SCRIPT_MINERACAO)]
        publica_reaberta, _ = carteira.abrir_carteira(arquivo, senha)
        assert_equal(publica_reaberta, publica)
        saidas = carteira.consultar_saidas(tx, cli, minerador.datadir_path)
        assert_equal(saidas[0].nValue, valor)
        carteira.assinar_com_arquivo(tx, saidas, arquivo, senha, ferramenta)
        assinatura = tx.wit.vtxinwit[0].scriptWitness.stack[0]

        # A mesma entrada financia dez pagamentos e uma saída de troco.
        lote = copy.deepcopy(tx)
        lote.wit.vtxinwit.clear()
        lote.vout = [
            CTxOut(100_000, b"\x52\x20" + hashlib.sha256(i.to_bytes(4, "little")).digest())
            for i in range(10)
        ]
        lote.vout.append(CTxOut(valor - 1_000_000 - 10_000, script_mldsa65))
        carteira.assinar_com_arquivo(lote, saidas, arquivo, senha, ferramenta)
        lote_hex = lote.serialize().hex()
        assert_equal(minerador.decoderawtransaction(lote_hex)["weight"], 7366)
        assert_equal(minerador.testmempoolaccept([lote_hex])[0]["allowed"], True)

        sem_testemunha = copy.deepcopy(tx)
        sem_testemunha.wit.vtxinwit = []
        chave_errada = copy.deepcopy(tx)
        chave_errada.wit.vtxinwit[0].scriptWitness.stack[1] = bytes(1952)
        assinatura_curta = copy.deepcopy(tx)
        assinatura_curta.wit.vtxinwit[0].scriptWitness.stack[0] = assinatura[:-1]
        adulterada = copy.deepcopy(tx)
        adulterada.vout[0].nValue -= 1
        com_scriptsig = copy.deepcopy(tx)
        com_scriptsig.vin[0].scriptSig = b"\x51"
        for variante in (sem_testemunha, chave_errada, assinatura_curta, adulterada, com_scriptsig):
            resultado = minerador.testmempoolaccept([variante.serialize().hex()])[0]
            assert_equal(resultado["allowed"], False)

        # Submete diretamente um bloco com compromisso de testemunha e PoW válidos.
        # Isso verifica o consenso independentemente da política da mempool.
        ponta = minerador.getbestblockhash()
        altura = minerador.getblockcount()
        def submeter(transacoes=(), premio=SCRIPT_MINERACAO):
            coinbase = create_coinbase(altura + 1, script_pubkey=premio)
            bloco = create_block(hashprev=int(ponta, 16), coinbase=coinbase, txlist=transacoes)
            add_witness_commitment(bloco)
            bloco.solve()
            rejeicao = par.submitblock(bloco.serialize().hex())
            assert_equal(par.getbestblockhash(), ponta)
            return rejeicao

        for variante in (sem_testemunha, chave_errada, assinatura_curta, adulterada, com_scriptsig):
            rejeicao = submeter([variante])
            assert rejeicao.startswith("block-script-verify-flag-failed"), rejeicao

        scripts_proibidos = {
            "P2PKH": "76a914" + "11" * 20 + "88ac",
            "P2SH": "a914" + "11" * 20 + "87",
            "P2WPKH": "0014" + "11" * 20,
            "P2WSH": "0020" + "11" * 32,
            "Taproot": "5120" + "11" * 32,
            "SegWit v3": "5320" + "11" * 32,
            "ML-DSA-65 com tamanho inválido": "5214" + "11" * 20,
            "P2A": "51024e73",
            "OP_TRUE": "51",
            "Script vazio": "",
        }
        for tipo, hex_script in scripts_proibidos.items():
            self.log.info("Verificando rejeição de %s", tipo)
            script = bytes.fromhex(hex_script)
            proibida = copy.deepcopy(tx)
            proibida.wit.vtxinwit.clear()
            proibida.vout = [CTxOut(valor - 10_000, script)]
            carteira.assinar_com_arquivo(proibida, saidas, arquivo, senha, ferramenta)
            resultado = minerador.testmempoolaccept([proibida.serialize().hex()])[0]
            assert_equal(resultado["reject-reason"], "bad-real26-output-script")
            assert_equal(submeter([proibida]), "bad-real26-output-script")
            assert_equal(submeter(premio=script), "bad-real26-output-script")

        txid = minerador.sendrawtransaction(tx.serialize().hex())
        self.sync_mempools(self.nodes[:2])
        assert txid in par.getrawmempool()
        [bloco_valido] = self.generatetodescriptor(minerador, 1, descritor, sync_fun=sync)
        assert txid in par.getblock(bloco_valido)["tx"]
        self.log.info("Gasto ML-DSA-65 aceito pelos dois nós e gasto adulterado rejeitado pela mempool e pelo consenso.")

        nome = "observacao-real26"
        minerador.createwallet(nome, disable_private_keys=True, blank=True)
        observacao = minerador.get_wallet_rpc(nome)
        rpc = carteira.conectar_no(cli, minerador.datadir_path)
        assert_equal(carteira.observar(rpc, endereco, nome), endereco)
        assert_equal(observacao.getwalletinfo()["private_keys_enabled"], False)
        assert_equal(observacao.getaddressinfo(endereco)["ismine"], True)
        assert_equal(observacao.getbalance(), 100)

        script_destino = SCRIPT_MINERACAO.hex()
        destino = minerador.decodescript(script_destino)["address"]
        legado = minerador.decodescript("0014" + "11" * 20)["address"]
        taxa = 10_000
        assert_raises(ValueError, carteira.montar_pagamento, rpc, publica, legado, COIN, taxa)
        assert_raises(ValueError, carteira.montar_pagamento, rpc, publica, destino, 101 * COIN, taxa)
        pagamento, moedas = carteira.montar_pagamento(rpc, publica, destino, 75 * COIN, taxa)
        assert_equal(len(pagamento.vin), 2)
        assert_equal(pagamento.vout[0].scriptPubKey.hex(), script_destino)
        assert_equal(pagamento.vout[0].nValue, 75 * COIN)
        assert_equal(pagamento.vout[1].scriptPubKey, script_mldsa65)
        assert_equal(pagamento.vout[1].nValue, 25 * COIN - taxa)

        # Uma cópia do arquivo cifrado com a senha restaura a capacidade de assinar.
        backup = arquivo.with_suffix(".backup")
        backup.write_bytes(arquivo.read_bytes())
        publica_backup, privada_backup = carteira.abrir_carteira(backup, senha)
        assert_equal(publica_backup, publica)
        restaurada = arquivo.with_suffix(".restaurada")
        senha_nova = "outra senha de teste"
        assert_equal(carteira.criar_carteira(restaurada, senha_nova, ferramenta, frase=frase), publica)
        # Mesmo material de chave, com novo sal e nonce no envelope.
        inicio = len(carteira.FORMATO)
        assert arquivo.read_bytes()[inicio:inicio + 28] != restaurada.read_bytes()[inicio:inicio + 28]
        publica_restaurada, privada_restaurada = carteira.abrir_carteira(restaurada, senha_nova)
        assert_equal(privada_restaurada, privada_backup)
        assert_equal(publica_restaurada, publica)
        carteira.assinar_com_arquivo(pagamento, moedas, restaurada, senha_nova, ferramenta)
        # O regtest normal exige a chave completa em cada entrada.
        com_referencia = copy.deepcopy(pagamento)
        com_referencia.wit.vtxinwit[1].scriptWitness.stack[1] = bytes(1)
        assert_equal(minerador.testmempoolaccept([com_referencia.serialize().hex()])[0]["allowed"], False)
        pagamento_id = minerador.sendrawtransaction(pagamento.serialize().hex())
        self.sync_mempools(self.nodes[:2])
        [bloco_pagamento] = self.generatetodescriptor(minerador, 1, descritor, sync_fun=sync)
        assert pagamento_id in par.getblock(bloco_pagamento)["tx"]
        assert_equal(observacao.getbalance(), Decimal(25 * COIN - taxa) / COIN)
        self.log.info("Carteira de observação sincronizada e pagamento com duas entradas e troco confirmado.")


    def testar_carteira_core(self, minerador, par):
        nome = "carteira-core-real26"
        senha = "senha de teste da carteira Core"
        minerador.createwallet(nome, passphrase=senha)
        nativa = minerador.get_wallet_rpc(nome)
        assert_raises_rpc_error(-13, "walletpassphrase", nativa.getreal26address)
        nativa.walletpassphrase(senha, 60)
        endereco = nativa.getreal26address()
        assert endereco.startswith("r26pq1z")
        assert_equal(nativa.getaddressinfo(endereco)["ismine"], True)

        def sincronizar():
            return self.sync_blocks(self.nodes[:2])
        self.generatetoaddress(minerador, 2, endereco, sync_fun=sincronizar)
        descritor = minerador.getdescriptorinfo(f"raw({SCRIPT_MINERACAO.hex()})")["descriptor"]
        self.generatetodescriptor(minerador, 100, descritor, sync_fun=sincronizar)

        # Reabre a base SQLite e comprova a persistência da chave e do endereço.
        minerador.unloadwallet(nome)
        minerador.loadwallet(nome)
        nativa = minerador.get_wallet_rpc(nome)
        assert_equal(nativa.getreal26address(), endereco)
        legado = minerador.decodescript("0014" + "22" * 20)["address"]
        destino = encode_segwit_address("r26pq", 2, SCRIPT_MINERACAO[2:])
        assert_raises_rpc_error(-13, "walletpassphrase", nativa.sendreal26, destino, 75, Decimal("0.0001"))
        nativa.walletpassphrase(senha, 60)
        assert_raises_rpc_error(-5, "endereços ML-DSA-65", nativa.sendreal26, legado, 1, Decimal("0.0001"))
        txid = nativa.sendreal26(destino, 75, Decimal("0.0001"))
        self.sync_mempools(self.nodes[:2])
        [bloco] = self.generatetodescriptor(minerador, 1, descritor, sync_fun=sincronizar)
        transacao = next(tx for tx in par.getblock(bloco, 2)["tx"] if tx["txid"] == txid)
        assert_equal(len(transacao["vin"]), 2)
        assert_equal(transacao["vout"][0]["value"], 75)
        assert_equal(transacao["vout"][1]["value"], Decimal("24.9999"))
        assert_equal(transacao["vout"][1]["scriptPubKey"]["address"], endereco)
        nativa.walletlock()
        assert_raises_rpc_error(-13, "walletpassphrase", nativa.sendreal26, destino, 1, Decimal("0.0001"))
        backup = Path(self.options.tmpdir) / "backup-core-real26.dat"
        nativa.backupwallet(str(backup))
        minerador.unloadwallet(nome)
        restaurada = "core-real26-restaurada"
        minerador.restorewallet(restaurada, str(backup))
        nativa_restaurada = minerador.get_wallet_rpc(restaurada)
        assert_equal(nativa_restaurada.getreal26address(), endereco)
        assert_raises_rpc_error(-13, "walletpassphrase", nativa_restaurada.sendreal26, destino, 1, Decimal("0.0001"))
        destinos = {
            encode_segwit_address("r26pq", 2, hashlib.sha256(i.to_bytes(4, "little")).digest()): Decimal("0.001")
            for i in range(10)
        }
        taxa = Decimal("0.0001")
        assert_raises_rpc_error(-13, "walletpassphrase", nativa_restaurada.sendreal26many, destinos, taxa)
        nativa_restaurada.walletpassphrase(senha, 60)
        assert_raises_rpc_error(-5, "endereços ML-DSA-65", nativa_restaurada.sendreal26many, {legado: 1}, taxa)
        lote = nativa_restaurada.sendreal26many(destinos, taxa)
        self.sync_mempools(self.nodes[:2])
        [bloco_lote] = self.generatetodescriptor(minerador, 1, descritor, sync_fun=sincronizar)
        pagamento_lote = next(tx for tx in par.getblock(bloco_lote, 2)["tx"] if tx["txid"] == lote)
        assert_equal(len(pagamento_lote["vin"]), 1)
        assert_equal(len(pagamento_lote["vout"]), 11)
        assert_equal(len(pagamento_lote["vin"][0]["txinwitness"]), 2)
        assert_equal(pagamento_lote["weight"], 7366)
        for saida in pagamento_lote["vout"][:-1]:
            assert_equal(saida["value"], destinos[saida["scriptPubKey"]["address"]])
        assert_equal(pagamento_lote["vout"][-1]["value"], Decimal("24.9898"))
        self.log.info("Carteira nativa restaurou a chave e confirmou dez pagamentos e troco com uma assinatura.")


if __name__ == "__main__":
    Real26Regtest(__file__).main()
