# Distribuído sob a licença MIT. Consulte COPYING.
"""Mede blocos quase cheios na testnet REAL-26 com referências canônicas."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import time

from test_framework.blocktools import add_witness_commitment, create_block, create_coinbase
from test_framework.messages import COIN, COutPoint, CTransaction, CTxIn, CTxOut, ser_vector, tx_from_hex
from test_framework.test_framework import BitcoinTestFramework, SkipTest
from test_framework.util import append_config, assert_equal


GENESE = "00008e6fbebecfe46f33a0ef6c0655cde4d796bb4638d21bf858b434d9e2e7ed"
LIMITE = 4_000_000
TRANSACOES = 597
DUPLAS = 150
ENTRADAS = TRANSACOES + DUPLAS
RODADAS = 3
VALOR_UTXO = COIN // 100
TAXA = 10_000


class CargaTestnetRefs(BitcoinTestFramework):
    def set_test_params(self):
        self.chain = "testnet4"
        self.num_nodes = 3
        self.setup_clean_chain = True
        self.noban_tx_relay = True

    def skip_test_if_missing_module(self):
        if not self.config["components"].getboolean("REAL26_EXPERIMENTAL_MLDSA65", fallback=False):
            raise SkipTest("A compilação não inclui ML-DSA-65.")

    def setup_network(self):
        self.add_nodes(self.num_nodes)
        for no in self.nodes:
            no.chain = "real26testrefs"
            append_config(no.datadir_path, ["real26test=1", "real26testrefs=1", "acceptnonstdtxn=0"])
        self.start_nodes()
        self.connect_nodes(0, 1)
        self.conectar_validador()

    def conectar_validador(self):
        self.connect_nodes(2, 0)
        self.connect_nodes(2, 1)

    def montar_bloco(self, no, coinbase, transacoes=()):
        pai = no.getbestblockhash()
        cabecalho = no.getblockheader(pai)
        horario = max(int(time.time()), cabecalho["mediantime"] + 1)
        bloco = create_block(int(pai, 16), coinbase=coinbase, ntime=horario, txlist=transacoes)
        bloco.nBits = int(cabecalho["bits"], 16)
        add_witness_commitment(bloco)
        bloco.solve()
        return bloco

    def run_test(self):
        for no in self.nodes:
            assert_equal(no.getbestblockhash(), GENESE)
        minerador, alternativo, validador = self.nodes
        ambiente = self.config["environment"]
        assinador = Path(ambiente["BUILDDIR"]) / "bin" / ("real26_mldsa65_sign_test" + ambiente["EXEEXT"])
        chaves = subprocess.check_output([assinador, "gerar"])
        origem = b"\x52\x20" + sha256(chaves[:1952]).digest()
        destino = b"\x52\x20" + sha256(subprocess.check_output([assinador, "gerar"])[:1952]).digest()
        anterior = CTxOut(VALOR_UTXO, origem)
        descritor = f"raw({origem.hex()})"
        fontes = []

        for altura in range(1, RODADAS + 1):
            coinbase = create_coinbase(altura, script_pubkey=origem)
            coinbase.vout = [anterior] * (ENTRADAS + 1)
            bloco = self.montar_bloco(minerador, coinbase)
            assert_equal(minerador.submitblock(bloco.serialize().hex()), None)
            fontes.append(coinbase.txid_int)
        self.generatetodescriptor(minerador, 100, descritor)

        def assinar(fonte, indices):
            tx = CTransaction()
            tx.version = 2
            tx.vin = [CTxIn(COutPoint(fonte, indice)) for indice in indices]
            tx.vout = [CTxOut(400_000, destino), CTxOut(len(indices) * VALOR_UTXO - 400_000 - TAXA, origem)]
            dados = chaves + tx.serialize_without_witness() + ser_vector([anterior] * len(indices))
            return subprocess.check_output([assinador, "assinar-tx-testnet-refs"], input=dados).hex()

        def trafego(no):
            mensagens = ("cmpctblock", "blocktxn", "block")
            return {
                nome: sum(par["bytesrecv_per_msg"].get(nome, 0) for par in no.getpeerinfo())
                for nome in mensagens
            }

        resultados = []
        for rodada, fonte in enumerate(fontes, 1):
            no = minerador if rodada % 2 else alternativo
            altura = no.getblockcount() + 1
            hexs = [
                assinar(fonte, [i, TRANSACOES + i] if i < DUPLAS else [i])
                for i in range(TRANSACOES)
            ]
            transacoes = [tx_from_hex(dados) for dados in hexs]
            assert_equal(sum(len(tx.vin) == 2 for tx in transacoes), DUPLAS)
            assert all(tx.wit.vtxinwit[1].scriptWitness.stack[1] == bytes(1) for tx in transacoes[:DUPLAS])

            coinbase = create_coinbase(altura, script_pubkey=origem, fees=TAXA * TRANSACOES)
            bloco = self.montar_bloco(no, coinbase, transacoes)
            assert 0.99 * LIMITE <= bloco.get_weight() <= LIMITE
            if rodada == 1:
                excedente = tx_from_hex(assinar(fonte, [ENTRADAS]))
                premio = create_coinbase(altura, script_pubkey=origem, fees=TAXA * (TRANSACOES + 1))
                acima = self.montar_bloco(no, premio, [*transacoes, excedente])
                assert acima.get_weight() > LIMITE
                assert_equal(validador.submitblock(acima.serialize().hex()), "bad-blk-weight")

            inicio = time.perf_counter()
            for dados in hexs:
                no.sendrawtransaction(dados)
            self.sync_mempools(wait=0.05, timeout=90)
            mempool_s = time.perf_counter() - inicio
            assert_equal(set(validador.getrawmempool()), {tx.txid_hex for tx in transacoes})
            antes = trafego(validador)

            inicio = time.perf_counter()
            assert_equal(no.submitblock(bloco.serialize().hex()), None)
            self.wait_until(lambda: validador.getbestblockhash() == bloco.hash_hex)
            receptor_s = time.perf_counter() - inicio
            depois = trafego(validador)
            self.sync_blocks()
            assert_equal(validador.getblockheader(bloco.hash_hex)["nTx"], TRANSACOES + 1)
            assert all(not no.getrawmempool() for no in self.nodes)
            amostra = {
                "altura": altura, "minerador": no.index, "transacoes": TRANSACOES, "duplas": DUPLAS,
                "peso": bloco.get_weight(), "bytes": len(bloco.serialize()),
                "mempool_s": round(mempool_s, 3), "receptor_s": round(receptor_s, 3),
                "p2p_bloco": {k: depois[k] - antes[k] for k in antes},
            }
            resultados.append(amostra)
            self.log.info("Bloco de carga %s", amostra)
            if rodada == 2:
                self.stop_node(2)
                [posterior] = self.generatetodescriptor(minerador, 1, descritor, sync_fun=self.no_op)
                self.sync_blocks(self.nodes[:2])
                self.start_node(2)
                assert_equal(validador.getbestblockhash(), bloco.hash_hex)
                self.conectar_validador()
                self.sync_blocks()
                assert_equal(validador.getbestblockhash(), posterior)
                self.log.info("Validador retomou a sincronização após reinício.")

        print("REAL26_RESULTADO:" + json.dumps(resultados), flush=True)


if __name__ == "__main__":
    CargaTestnetRefs(__file__).main()
