#!/usr/bin/env python3
# Distribuído sob a licença MIT. Consulte COPYING.
"""Testa ASERT, dois mineradores e pagamentos ML-DSA-65 no mesmo laboratório."""

from decimal import Decimal

from feature_real26_asert import BITS_INICIAIS, BITS_LIMITE, INTERVALO, alvo_esperado
from test_framework.blocktools import add_witness_commitment, create_block, create_coinbase
from test_framework.test_framework import BitcoinTestFramework, SkipTest
from test_framework.util import append_config, assert_equal, assert_raises_rpc_error


GENESE = "0145759a8518385c134aa276159d91dc321a6cbd958156b617ce5845bad9fad8"
GENESE_TESTNET = "0000058319331d5a63c4d88f6338cce3b9deb43110246e701b4508dc4c15b2c2"
TEMPO_TESTNET = 1795132800
BITS_TESTNET = 0x1C10E331
REGRAS = {"rules": ["segwit"]}


class Real26AsertPQ(BitcoinTestFramework):
    def add_options(self, parser):
        parser.add_argument("--compartilhado", action="store_true", help="Executa o teste na testnet ASERT.")

    def set_test_params(self):
        if self.options.compartilhado:
            self.chain = "testnet4"
        self.num_nodes = 3
        self.setup_clean_chain = True
        self.noban_tx_relay = True

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()
        if not self.config["components"].getboolean("REAL26_EXPERIMENTAL_MLDSA65", fallback=False):
            raise SkipTest("A compilação não inclui ML-DSA-65.")

    def setup_network(self):
        self.add_nodes(self.num_nodes)
        for node in self.nodes:
            if self.options.compartilhado:
                append_config(node.datadir_path, ["real26test=1", "real26testrefs=1", "real26testasert=1"])
                node.chain = "real26testasert-v2"
            else:
                append_config(node.datadir_path, ["real26asert=1", "real26dev=1"])
                node.chain = "real26asert-pq"
        if self.options.compartilhado:
            self.start_nodes([[*node.extra_args, f"-mocktime={TEMPO_TESTNET + 6 * 86400}"] for node in self.nodes])
        else:
            self.start_nodes()
        self.connect_nodes(0, 2)
        self.connect_nodes(1, 2)

    def run_test(self):
        primeiro, segundo, validador = self.nodes
        compartilhado = self.options.compartilhado
        genese = GENESE_TESTNET if compartilhado else GENESE
        prefixo = "r26s1z" if compartilhado else "r26ap1z"
        t0 = primeiro.getblockheader(genese)["time"]
        horario = t0
        carteiras, premios = [], []
        for node in self.nodes:
            assert_equal(node.getbestblockhash(), genese)
            # Registre os endereços antes dos pagamentos na cronologia do ensaio.
            if not compartilhado:
                node.setmocktime(t0)
            node.createwallet("laboratorio", passphrase="senha descartavel de ensaio", load_on_startup=True)
            carteira = node.get_wallet_rpc("laboratorio")
            carteira.walletpassphrase("senha descartavel de ensaio", 3600)
            endereco = carteira.getreal26address()
            assert endereco.startswith(prefixo)
            carteiras.append(carteira)
            premios.append(bytes.fromhex(node.validateaddress(endereco)["scriptPubKey"]))
            if not compartilhado:
                node.setmocktime(t0 + 16 * 3600)

        if compartilhado:
            self.log.info("Verificando o alvo de lançamento seis dias após o gênese")
            for node in self.nodes:
                modelo = node.getblocktemplate(REGRAS)
                assert_equal(modelo["height"], 1)
                assert_equal(int(modelo["bits"], 16), BITS_TESTNET)
            return

        def minerar(indice, intervalo, pares, incluir_pagamento=False):
            nonlocal horario
            node = self.nodes[indice]
            modelo = node.getblocktemplate(REGRAS)
            esperado = alvo_esperado(modelo["height"] - 1, horario - t0, BITS_INICIAIS, BITS_LIMITE)
            assert_equal(int(modelo["bits"], 16), esperado)
            horario += intervalo
            coinbase = create_coinbase(modelo["height"], script_pubkey=premios[indice], nValue=0)
            coinbase.vout[0].nValue = modelo["coinbasevalue"]
            bloco = create_block(coinbase=coinbase, ntime=horario, tmpl=modelo,
                                 txlist=[tx["data"] for tx in modelo["transactions"]])
            if incluir_pagamento:
                assert_equal(len(bloco.vtx), 2)
            add_witness_commitment(bloco)
            bloco.solve()
            assert_equal(node.submitblock(bloco.serialize().hex()), None)
            self.sync_blocks(nodes=pares, wait=0.05)

        self.log.info("Dois mineradores alternam blocos sob a meta e amadurecem suas recompensas")
        for i in range(106):
            minerar(i % 2, INTERVALO, self.nodes)
        assert_equal(primeiro.getblockcount(), 106)

        self.log.info("Simulando blocos acelerados, saída e retorno do segundo minerador")
        bits_originais = int(primeiro.getblocktemplate(REGRAS)["bits"], 16)
        for i in range(12):
            minerar(i % 2, 60, self.nodes)
        bits_rapidos = int(primeiro.getblocktemplate(REGRAS)["bits"], 16)
        assert bits_rapidos < bits_originais
        self.disconnect_nodes(1, 2)
        for _ in range(8):
            minerar(0, 900, [primeiro, validador])
        assert_equal(segundo.getblockcount(), 118)
        assert int(primeiro.getblocktemplate(REGRAS)["bits"], 16) > bits_rapidos
        self.connect_nodes(1, 2)
        self.sync_blocks()

        self.log.info("O segundo minerador confirma um pagamento ML-DSA-65 criado pelo primeiro")
        senha = "senha descartavel de ensaio"
        carteira_origem = carteiras[0]
        destino = carteiras[2].getreal26address()
        carteira_origem.walletlock()
        assert_raises_rpc_error(-14, "senha da carteira", carteira_origem.verifyreal26passphrase, "errada")
        assert_raises_rpc_error(-14, "senha da carteira", carteira_origem.sendreal26,
                                destino, 30, Decimal("0.001"), "errada")
        assert_equal(primeiro.getrawmempool(), [])
        assert_equal(carteira_origem.verifyreal26passphrase(senha), True)
        assert_equal(carteira_origem.getwalletinfo()["unlocked_until"], 0)
        txid = carteira_origem.sendreal26(destino, 30, Decimal("0.001"), senha)
        assert_equal(carteira_origem.getwalletinfo()["unlocked_until"], 0)
        self.sync_mempools()
        bruto = segundo.getrawtransaction(txid, True)
        assert_equal(len(bruto["vin"]), 2)
        assert_equal(bruto["vin"][1]["txinwitness"][1], "00")
        minerar(1, INTERVALO, self.nodes, incluir_pagamento=True)
        recebido = carteiras[2].gettransaction(txid)
        assert_equal(recebido["confirmations"], 1)
        assert_equal(recebido["amount"], 30)
        assert_equal(primeiro.getblockcount(), 127)

        txid_lote = carteira_origem.sendreal26many({destino: Decimal("1")}, Decimal("0.001"), senha)
        assert_equal(carteira_origem.getwalletinfo()["unlocked_until"], 0)
        self.sync_mempools()
        assert txid_lote in segundo.getrawmempool()

        modelo = primeiro.getblocktemplate(REGRAS)
        legado = create_block(height=modelo["height"], ntime=horario + INTERVALO, tmpl=modelo)
        legado.solve()
        for node in self.nodes:
            assert_equal(node.submitblock(legado.serialize().hex()), "bad-real26-output-script")


if __name__ == "__main__":
    Real26AsertPQ(__file__).main()
