#!/usr/bin/env python3
# Distribuído sob a licença MIT. Consulte o arquivo COPYING.
"""Exercita a prova de trabalho e o pagamento ML-DSA-65 na testnet REAL-26."""

from copy import deepcopy
from decimal import Decimal
import hashlib
from io import BytesIO
from pathlib import Path
import subprocess
import sys
import time

from test_framework.blocktools import add_witness_commitment, create_block, create_coinbase
from test_framework.messages import COIN, CBlock, COutPoint, CTransaction, CTxIn, CTxOut, ser_vector, tx_from_hex, uint256_from_compact
from test_framework.test_framework import BitcoinTestFramework, SkipTest
from test_framework.util import append_config, assert_equal


GENESE = "000f21da01c7bb9dfb2a2e1c441c1b22587639216626312523249fc990eceaa4"
GENESE_REFS = "00008e6fbebecfe46f33a0ef6c0655cde4d796bb4638d21bf858b434d9e2e7ed"
GENESE_ENSAIO = "0007326bf77a1489a5e6ee7aa98affe5baac14aa7f2b694a86e2b54c8ae24733"
BITS_INICIAIS = 0x1F0FFFFF
BITS_AJUSTADOS = 0x1F03FFFF


class Real26Testnet(BitcoinTestFramework):
    def add_options(self, parser):
        parser.add_argument("--ensaio", action="store_true", help="Testa o gênese e o subsídio da rede privada.")
        parser.add_argument("--refs", action="store_true", help="Testa a variante com referências de chave.")

    def set_test_params(self):
        self.chain = "testnet4"
        self.num_nodes = 3
        self.setup_clean_chain = True
        self.noban_tx_relay = True
        self.uses_wallet = True
        self.extra_args = [["-dnsseed=0", "-fixedseeds=0", "-acceptnonstdtxn=0"] for _ in range(3)]

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()
        if not self.config["components"].getboolean("REAL26_EXPERIMENTAL_MLDSA65", fallback=False):
            raise SkipTest("A compilação não inclui ML-DSA-65.")

    def setup_network(self):
        self.add_nodes(self.num_nodes, self.extra_args)
        for node in self.nodes:
            node.chain = "real26testrefs" if self.options.refs else "real26testnet"
            flags = ["real26test=1"]
            if self.options.refs or self.options.ensaio:
                node.chain = "real26testrefs"
                flags.append("real26testrefs=1")
            if self.options.ensaio:
                node.chain = "real26ensaio"
                flags.append("real26ensaio=1")
            append_config(node.datadir_path, flags)
        self.start_nodes()
        self.connect_nodes(0, 2)
        self.connect_nodes(1, 2)

    def run_test(self):
        principal, alternativo, validador = self.nodes
        ensaio = self.options.ensaio
        referencias = self.options.refs or ensaio
        genese = GENESE_ENSAIO if ensaio else GENESE_REFS if referencias else GENESE
        subsidio = 25 if ensaio else 50
        for no in self.nodes:
            assert_equal(no.getbestblockhash(), genese)
        if ensaio:
            sys.path.insert(0, self.config["environment"]["SRCDIR"])
            from experimentos.mensagem_genese import montar_coinbase

            bloco_genese = CBlock()
            bloco_genese.deserialize(BytesIO(bytes.fromhex(principal.getblock(genese, 0))))
            assert_equal(len(bloco_genese.vtx), 1)
            assert_equal(bloco_genese.vtx[0].serialize(), montar_coinbase().serialize())
            assert bloco_genese.is_valid()
        senha = "senha descartável do teste"
        principal.createwallet("minerador", passphrase=senha)
        alternativo.createwallet("alternativo", passphrase=senha)
        validador.createwallet("destinatario", passphrase=senha, load_on_startup=True)
        carteira = principal.get_wallet_rpc("minerador")
        segunda = alternativo.get_wallet_rpc("alternativo")
        destinatario = validador.get_wallet_rpc("destinatario")
        for wallet in (carteira, segunda, destinatario):
            wallet.walletpassphrase(senha, 300)
        remetente = carteira.getreal26address()
        recebedor = destinatario.getreal26address()
        prefixo = "r26e1z" if ensaio else "r26tr1z" if referencias else "r26t1z"
        assert remetente.startswith(prefixo)
        assert recebedor.startswith(prefixo)
        script = bytes.fromhex(principal.validateaddress(remetente)["scriptPubKey"])
        inicio = principal.getblockheader(genese)["time"]

        def bloco(pai, altura, horario, bits, premio=script, transacoes=(), recompensa=subsidio):
            coinbase = create_coinbase(altura, script_pubkey=premio, nValue=recompensa, halving_period=210_000)
            candidato = create_block(int(pai, 16), coinbase=coinbase, ntime=horario, txlist=transacoes)
            candidato.nBits = bits
            add_witness_commitment(candidato)
            return candidato

        self.log.info("Provando que a testnet exige trabalho e rejeita recompensas legadas")
        invalido = bloco(genese, 1, inicio + 60, BITS_INICIAIS)
        while invalido.hash_int <= uint256_from_compact(BITS_INICIAIS):
            invalido.nNonce += 1
        assert_equal(principal.submitblock(invalido.serialize().hex()), "high-hash")
        legado = bloco(genese, 1, inicio + 60, BITS_INICIAIS, premio=b"\x51")
        legado.solve()
        assert_equal(principal.submitblock(legado.serialize().hex()), "bad-real26-output-script")
        assert_equal(principal.getblockcount(), 0)
        if ensaio:
            excesso = bloco(genese, 1, inicio + 60, BITS_INICIAIS, recompensa=26)
            excesso.solve()
            assert_equal(principal.submitblock(excesso.serialize().hex()), "bad-cb-amount")
            assert_equal(principal.getblockcount(), 0)

        self.log.info("Minerando o primeiro período e verificando o ajuste de dificuldade")
        ambiente = self.config["environment"]
        assinador = Path(ambiente["BUILDDIR"]) / "bin" / ("real26_mldsa65_sign_test" + ambiente["EXEEXT"])
        chaves_dev = subprocess.check_output([assinador, "gerar"])
        script_dev = b"\x52\x20" + hashlib.sha256(chaves_dev[:1952]).digest()
        ponta = genese
        for altura in range(1, 144):
            premio = script_dev if altura == 1 else script
            candidato = bloco(ponta, altura, inicio + 60 * altura, BITS_INICIAIS, premio=premio)
            if altura == 1:
                recompensa_dev = candidato.vtx[0].txid_int
            candidato.solve()
            assert_equal(principal.submitblock(candidato.serialize().hex()), None)
            ponta = candidato.hash_hex

        agora = int(time.time())
        desatualizado = bloco(ponta, 144, agora, BITS_INICIAIS)
        desatualizado.solve()
        assert_equal(principal.submitblock(desatualizado.serialize().hex()), "bad-diffbits")
        ajustado = bloco(ponta, 144, agora, BITS_AJUSTADOS)
        ajustado.solve()
        assert_equal(principal.submitblock(ajustado.serialize().hex()), None)
        self.sync_blocks()
        assert_equal(validador.getblockheader(ajustado.hash_hex)["bits"], "1f03ffff")
        assert_equal(principal.getblocktemplate({"rules": ["segwit"]})["bits"], "1f03ffff")

        self.log.info("Rejeitando assinatura feita no domínio criptográfico do regtest")
        gasto_dev = CTransaction()
        gasto_dev.version = 2
        gasto_dev.vin = [CTxIn(COutPoint(recompensa_dev, 0))]
        gasto_dev.vout = [CTxOut(subsidio * COIN - 10_000, script)]
        entrada = chaves_dev + gasto_dev.serialize_without_witness() + ser_vector([CTxOut(subsidio * COIN, script_dev)])
        gasto_hex = subprocess.check_output([assinador, "assinar-tx"], input=entrada).hex()
        assert_equal(principal.testmempoolaccept([gasto_hex])[0]["allowed"], False)
        bloco_dev = bloco(ajustado.hash_hex, 145, agora + 1, BITS_AJUSTADOS, transacoes=[tx_from_hex(gasto_hex)])
        bloco_dev.solve()
        rejeicao = validador.submitblock(bloco_dev.serialize().hex())
        assert rejeicao.startswith("block-script-verify-flag-failed"), rejeicao

        # Os blocos de retarget usam datas anteriores à criação das carteiras.
        numero_recompensas = 102 if referencias else 101
        recompensas = self.generatetoaddress(principal, numero_recompensas, remetente, 10_000_000)
        assert_equal(len(recompensas), numero_recompensas)
        assert_equal(principal.getblock(recompensas[0], 2)["tx"][0]["vout"][0]["value"], subsidio)
        valor = Decimal("37.5") if ensaio else 75 if referencias else 1
        assert carteira.getbalance() > valor

        self.log.info("Confirmando pagamento pós-quântico e provocando uma reorganização")
        self.disconnect_nodes(1, 2)
        txid = carteira.sendreal26(recebedor, valor, Decimal("0.0001"))
        self.sync_mempools(self.nodes[::2])
        if referencias:
            pagamento = tx_from_hex(validador.getrawtransaction(txid))
            assert_equal(len(pagamento.vin), 2)
            chave = pagamento.wit.vtxinwit[0].scriptWitness.stack[1]
            assert_equal(len(chave), 1952)
            assert_equal(pagamento.wit.vtxinwit[1].scriptWitness.stack[1], bytes(1))

            redundante = deepcopy(pagamento)
            redundante.wit.vtxinwit[1].scriptWitness.stack[1] = chave
            assert_equal(redundante.txid_hex, txid)
            pai = principal.getbestblockhash()
            horario = principal.getblockheader(pai)["mediantime"] + 1
            candidato = bloco(pai, principal.getblockcount() + 1, horario, BITS_AJUSTADOS, transacoes=[redundante])
            candidato.solve()
            motivo = validador.submitblock(candidato.serialize().hex())
            assert motivo and motivo.startswith("block-script-verify-flag-failed"), motivo
            assert_equal(validador.getbestblockhash(), pai)
        [confirmado] = self.generatetoaddress(principal, 1, remetente, sync_fun=lambda: self.sync_blocks(self.nodes[::2]))
        assert txid in validador.getblock(confirmado)["tx"]
        assert_equal(destinatario.gettransaction(txid)["confirmations"], 1)

        concorrente = self.generatetoaddress(alternativo, 2, segunda.getreal26address(), sync_fun=self.no_op)[-1]
        self.connect_nodes(1, 2)
        self.sync_blocks()
        assert_equal(validador.getbestblockhash(), concorrente)
        assert_equal(destinatario.gettransaction(txid)["confirmations"], 0)
        assert txid in principal.getrawmempool()
        assert txid in validador.getrawmempool()
        [reconfirmado] = self.generatetoaddress(principal, 1, remetente)
        assert txid in validador.getblock(reconfirmado)["tx"]
        assert_equal(destinatario.gettransaction(txid)["confirmations"], 1)
        assert_equal(destinatario.getbalance(), valor)

        self.log.info("Reabrindo o nó validador a partir da cadeia persistida")
        self.stop_node(2)
        [posterior] = self.generatetoaddress(principal, 1, remetente, sync_fun=self.no_op)
        self.start_node(2)
        assert_equal(validador.getbestblockhash(), reconfirmado)
        self.connect_nodes(0, 2)
        self.connect_nodes(1, 2)
        self.sync_blocks()
        assert_equal(validador.getbestblockhash(), posterior)
        original = validador.get_wallet_rpc("destinatario")
        assert_equal(original.gettransaction(txid)["confirmations"], 2)
        self.log.info("Restaurando a carteira criptografada e confirmando um gasto com a chave recuperada")
        backup = Path(self.options.tmpdir) / "backup-testnet-real26.dat"
        original.backupwallet(str(backup))
        validador.unloadwallet("destinatario")
        validador.restorewallet("destinatario-restaurado", str(backup))
        restaurada = validador.get_wallet_rpc("destinatario-restaurado")
        assert_equal(restaurada.getreal26address(), recebedor)
        restaurada.walletpassphrase(senha, 300)
        gasto_restaurado = restaurada.sendreal26(remetente, Decimal("0.5"), Decimal("0.0001"))
        self.sync_mempools()
        [final] = self.generatetoaddress(principal, 1, remetente)
        assert gasto_restaurado in alternativo.getblock(final)["tx"]


if __name__ == "__main__":
    Real26Testnet(__file__).main()
