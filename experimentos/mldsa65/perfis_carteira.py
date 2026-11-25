# Distribuído sob a licença MIT. Consulte COPYING.
"""Compara gastos da carteira em saldos com fragmentação controlada."""
from decimal import Decimal
from hashlib import sha256
import json
import time

from test_framework.blocktools import create_block, create_coinbase
from test_framework.messages import COIN, CTxOut, tx_from_hex
from test_framework.segwit_addr import encode_segwit_address
from test_framework.test_framework import BitcoinTestFramework, SkipTest
from test_framework.util import append_config, assert_equal


PERFIS = {
    "poucas_saidas_grandes": [8 * COIN] * 4,
    "muitas_saidas_pequenas": [COIN // 4] * 128,
    "saldo_misto": [5 * COIN] * 4 + [COIN // 4] * 48,
}
PAGAMENTOS = (
    ("0.60", 1), ("1.40", 1), ("2.50", 10), ("0.85", 1),
    ("3.20", 1), ("1.25", 10), ("0.45", 1), ("4.30", 1),
    ("2.10", 10), ("5.40", 1), ("3.60", 1), ("1.75", 10),
)
TAXA = Decimal("0.0001")
PREMIO = "raw(5220" + "01" * 32 + ")"


class PerfisCarteira(BitcoinTestFramework):
    def set_test_params(self):
        self.num_nodes = 2
        self.setup_clean_chain = True

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()
        if not self.config["components"].getboolean("REAL26_EXPERIMENTAL_MLDSA65", fallback=False):
            raise SkipTest("A compilação não inclui ML-DSA-65.")

    def setup_network(self):
        self.add_nodes(self.num_nodes)
        for no, diretorio in zip(self.nodes, ("real26mldsa-pq", "real26refs-v2")):
            no.chain = diretorio
            opcoes = ["real26dev=1"]
            if diretorio == "real26refs-v2":
                opcoes.append("real26refs=1")
            append_config(no.datadir_path, opcoes)
        self.start_nodes()

    def run_test(self):
        destinos = [
            encode_segwit_address("r26pq", 2, sha256(f"destino {i}".encode()).digest())
            for i in range(10)
        ]
        no_normal, no_refs = self.nodes
        carteiras_normais = self.financiar(no_normal)
        carteiras_refs = self.financiar(no_refs)
        resultados = {}

        for perfil in PERFIS:
            amostras = []
            for valor, quantidade in PAGAMENTOS:
                valor = Decimal(valor)
                normal = self.pagar(no_normal, carteiras_normais[perfil], destinos, valor, quantidade)
                refs = self.pagar(no_refs, carteiras_refs[perfil], destinos, valor, quantidade)
                assert_equal(normal["entradas"], refs["entradas"])
                assert_equal(normal["saidas"], refs["saidas"])
                assert_equal(normal["chaves_completas"], normal["entradas"])
                assert_equal(refs["chaves_completas"], 1)
                assert_equal(normal["peso"] - refs["peso"], 1953 * (normal["entradas"] - 1))
                amostras.append({"valor": str(valor), "destinatarios": quantidade, "normal": normal, "refs": refs})

            peso_normal = sum(a["normal"]["peso"] for a in amostras)
            peso_refs = sum(a["refs"]["peso"] for a in amostras)
            orcamento = 4_000_000 - 1_000
            resumo = {
                "transacoes": len(amostras),
                "pagamentos": sum(a["destinatarios"] for a in amostras),
                "varias_entradas": sum(a["normal"]["entradas"] > 1 for a in amostras),
                "total_entradas": sum(a["normal"]["entradas"] for a in amostras),
                "peso_normal": peso_normal,
                "peso_refs": peso_refs,
                "reducao_percentual": round(100 * (peso_normal - peso_refs) / peso_normal, 2),
                "tx_por_bloco_normal": orcamento * len(amostras) // peso_normal,
                "tx_por_bloco_refs": orcamento * len(amostras) // peso_refs,
            }
            resultados[perfil] = {"resumo": resumo, "amostras": amostras}
            self.log.info("%s %s", perfil, resumo)

        print("REAL26_RESULTADO:" + json.dumps(resultados), flush=True)

    def financiar(self, no):
        carteiras = {}
        senha = "temporaria do ensaio"
        for altura, (perfil, valores) in enumerate(PERFIS.items(), 1):
            no.createwallet(perfil, passphrase=senha)
            carteira = no.get_wallet_rpc(perfil)
            carteira.walletpassphrase(senha, 300)
            endereco = carteira.getreal26address()
            script = bytes.fromhex(no.validateaddress(endereco)["scriptPubKey"])
            coinbase = create_coinbase(altura, script_pubkey=script)
            coinbase.vout = [CTxOut(valor, script) for valor in valores]
            pai = no.getbestblockhash()
            horario = max(int(time.time()), no.getblockheader(pai)["mediantime"] + 1)
            bloco = create_block(int(pai, 16), coinbase=coinbase, ntime=horario)
            bloco.solve()
            assert_equal(no.submitblock(bloco.serialize().hex()), None)
            carteiras[perfil] = carteira

        self.generatetodescriptor(no, 100, PREMIO, sync_fun=self.no_op)
        for carteira in carteiras.values():
            assert_equal(carteira.getbalance(), 32)
        return carteiras

    def pagar(self, no, carteira, destinos, valor, quantidade):
        if quantidade == 1:
            txid = carteira.sendreal26(destinos[0], valor, TAXA)
        else:
            txid = carteira.sendreal26many({destino: valor / quantidade for destino in destinos[:quantidade]}, TAXA)
        tx = tx_from_hex(no.getrawtransaction(txid))
        assert_equal(len(tx.vout), quantidade + 1)
        assert_equal(sum(out.nValue for out in tx.vout[:quantidade]), int(valor * COIN))
        [bloco] = self.generatetodescriptor(no, 1, PREMIO, sync_fun=self.no_op)
        assert txid in no.getblock(bloco)["tx"]
        assert_equal(carteira.gettransaction(txid)["fee"], -TAXA)
        return {
            "entradas": len(tx.vin),
            "saidas": len(tx.vout),
            "chaves_completas": sum(len(w.scriptWitness.stack[1]) == 1952 for w in tx.wit.vtxinwit),
            "peso": tx.get_weight(),
        }


if __name__ == "__main__":
    PerfisCarteira(__file__).main()
