#!/usr/bin/env python3
# Distribuído sob a licença MIT. Consulte COPYING.
"""Verifica variantes de testemunha ML-DSA-65 na mempool e em blocos compactos."""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import subprocess

from test_framework.blocktools import add_witness_commitment, create_block, create_coinbase
from test_framework.messages import (
    COIN, MAGIC_BYTES, MSG_CMPCT_BLOCK, BlockTransactions, CBlockHeader, COutPoint, CTransaction, CTxIn, CTxOut,
    HeaderAndShortIDs, msg_blocktxn, msg_cmpctblock, msg_headers, msg_sendcmpct, ser_vector, tx_from_hex,
)
from test_framework.p2p import P2PInterface, p2p_lock
from test_framework.test_framework import BitcoinTestFramework, SkipTest
from test_framework.util import append_config, assert_equal


class Real26Refs(BitcoinTestFramework):
    def set_test_params(self):
        self.num_nodes = 3
        self.setup_clean_chain = True

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()
        if not self.config["components"].getboolean("REAL26_EXPERIMENTAL_MLDSA65", fallback=False):
            raise SkipTest("A compilação não inclui ML-DSA-65.")

    def setup_network(self):
        self.add_nodes(self.num_nodes)
        for node in self.nodes[:2]:
            node.chain = "real26refs-v2"
            append_config(node.datadir_path, ["real26dev=1", "real26refs=1"])
        self.nodes[2].chain = "real26mldsa-pq"
        append_config(self.nodes[2].datadir_path, ["real26dev=1"])
        self.start_nodes()

    def run_test(self):
        minerador, receptor, normal = self.nodes
        assert_equal(minerador.getbestblockhash(), "3259f716dc16d1f59dd6b05a245a5ac268a1c8bc788e3304878bc0a0bc873405")
        assert minerador.getbestblockhash() != normal.getbestblockhash()
        ambiente = self.config["environment"]
        assinador = Path(ambiente["BUILDDIR"]) / "bin" / ("real26_mldsa65_sign_test" + ambiente["EXEEXT"])
        chaves = subprocess.check_output([assinador, "gerar"])
        origem = b"\x52\x20" + sha256(chaves[:1952]).digest()
        anterior = CTxOut(COIN, origem)
        fontes = []
        def sincronizar_laboratorio():
            return self.sync_blocks(self.nodes[:2])
        self.connect_nodes(1, 0)
        for altura in range(1, 4):
            coinbase = create_coinbase(altura, script_pubkey=origem)
            coinbase.vout = [anterior] * altura
            for no in (minerador, normal):
                pai = no.getbestblockhash()
                horario = no.getblockheader(pai)["mediantime"] + 1
                bloco = create_block(int(pai, 16), coinbase=coinbase, ntime=horario)
                bloco.solve()
                assert_equal(no.submitblock(bloco.serialize().hex()), None)
            fontes.append(coinbase.txid_int)
        self.generatetodescriptor(minerador, 100, f"raw({origem.hex()})", sync_fun=sincronizar_laboratorio)
        self.generatetodescriptor(normal, 100, f"raw({origem.hex()})", sync_fun=self.no_op)

        self.disconnect_nodes(1, 0)
        MAGIC_BYTES["real26refs-v2"] = bytes.fromhex("b493d597")
        peer = receptor.add_p2p_connection(P2PInterface())
        peer.send_and_ping(msg_sendcmpct(announce=False, version=2))

        for entradas, fonte in enumerate(fontes, 1):
            original = CTransaction()
            original.version = 2
            original.vin = [CTxIn(COutPoint(fonte, i)) for i in range(entradas)]
            taxa = 10_000
            original.vout = [CTxOut(entradas * COIN - taxa, origem)]
            dados = chaves + original.serialize_without_witness() + ser_vector([anterior] * entradas)
            dev = tx_from_hex(subprocess.check_output([assinador, "assinar-tx"], input=dados).hex())
            minerada = tx_from_hex(subprocess.check_output([assinador, "assinar-tx-refs"], input=dados).hex())
            txid = minerada.txid_hex
            assert_equal(dev.txid_hex, txid)
            assert_equal(minerada.wit.vtxinwit[0].scriptWitness.stack[1], chaves[:1952])
            assert all(w.scriptWitness.stack[1] == bytes(1) for w in minerada.wit.vtxinwit[1:])

            # Mesmas saídas anteriores nas duas cadeias, com assinaturas
            # distintas. Ajusta a codificação para isolar o teste de domínio.
            dev_com_referencias = deepcopy(dev)
            for testemunha in dev_com_referencias.wit.vtxinwit[1:]:
                testemunha.scriptWitness.stack[1] = bytes(1)
            lab_com_chaves = deepcopy(minerada)
            for testemunha in lab_com_chaves.wit.vtxinwit[1:]:
                testemunha.scriptWitness.stack[1] = chaves[:1952]
            assert_equal(normal.testmempoolaccept([dev.serialize().hex()])[0]["allowed"], True)
            assert_equal(normal.testmempoolaccept([lab_com_chaves.serialize().hex()])[0]["allowed"], False)
            assert_equal(receptor.testmempoolaccept([dev_com_referencias.serialize().hex()])[0]["allowed"], False)
            assert_equal(receptor.testmempoolaccept([minerada.serialize().hex()])[0]["allowed"], True)
            if entradas > 1:
                assert_equal(receptor.testmempoolaccept([lab_com_chaves.serialize().hex()])[0]["allowed"], False)
            if entradas == 3:
                encadeada = deepcopy(minerada)
                encadeada.wit.vtxinwit[2].scriptWitness.stack[1] = bytes([1])
                assert_equal(receptor.testmempoolaccept([encadeada.serialize().hex()])[0]["allowed"], False)
            if entradas == 3:
                assert_equal(receptor.sendrawtransaction(minerada.serialize().hex()), txid)
            assert_equal(minerador.sendrawtransaction(minerada.serialize().hex()), txid)

            altura = minerador.getblockcount() + 1
            coinbase = create_coinbase(altura, script_pubkey=origem, fees=taxa)
            pai = minerador.getbestblockhash()
            horario = minerador.getblockheader(pai)["mediantime"] + 1
            if entradas > 1:
                candidato = create_block(int(pai, 16), coinbase=deepcopy(coinbase), ntime=horario, txlist=[lab_com_chaves])
                add_witness_commitment(candidato)
                candidato.solve()
                motivo = receptor.submitblock(candidato.serialize().hex())
                assert motivo and motivo.startswith("block-script-verify-flag-failed"), motivo
                assert_equal(receptor.getbestblockhash(), pai)

            bloco = create_block(int(pai, 16), coinbase=coinbase, ntime=horario, txlist=[minerada])
            add_witness_commitment(bloco)
            bloco.solve()
            assert_equal(minerador.submitblock(bloco.serialize().hex()), None)

            with p2p_lock:
                peer.last_message.pop("getblocktxn", None)
            peer.send_and_ping(msg_headers([CBlockHeader(bloco)]))
            peer.wait_for_getdata([bloco.hash_int])
            assert_equal(peer.last_message["getdata"].inv[0].type, MSG_CMPCT_BLOCK)
            compacto = HeaderAndShortIDs()
            compacto.initialize_from_block(bloco, use_witness=True)
            peer.send_and_ping(msg_cmpctblock(compacto.to_p2p()))
            if entradas < 3:
                pedido = peer.last_message["getblocktxn"].block_txn_request
                assert_equal(pedido.blockhash, bloco.hash_int)
                assert_equal(pedido.to_absolute(), [1])
                assert_equal(receptor.getbestblockhash(), pai)
                resposta = msg_blocktxn()
                resposta.block_transactions = BlockTransactions(blockhash=bloco.hash_int, transactions=[minerada])
                peer.send_and_ping(resposta)

            self.wait_until(lambda: receptor.getbestblockhash() == bloco.hash_hex)
            if entradas == 3:
                with p2p_lock:
                    assert "getblocktxn" not in peer.last_message
            assert_equal(receptor.getrawmempool(), [])
            assert_equal(receptor.getrawtransaction(txid, False, bloco.hash_hex), minerada.serialize().hex())
            receptor.invalidateblock(bloco.hash_hex)
            assert_equal(receptor.getbestblockhash(), pai)
            assert_equal(receptor.getrawtransaction(txid), minerada.serialize().hex())
            receptor.reconsiderblock(bloco.hash_hex)
            assert_equal(receptor.getbestblockhash(), bloco.hash_hex)
            assert_equal(receptor.getrawmempool(), [])
            self.log.info("Rodada %d: testemunha minerada preservada após confirmação e reorganização.", entradas)
        self.testar_carteira(minerador)


    def testar_carteira(self, minerador):
        senha = "senha temporária de laboratório"
        minerador.createwallet("refs", passphrase=senha)
        carteira = minerador.get_wallet_rpc("refs")
        carteira.walletpassphrase(senha, 120)
        endereco = carteira.getreal26address()
        self.generatetoaddress(minerador, 102, endereco, sync_fun=self.no_op)
        txid = carteira.sendreal26(endereco, 75, Decimal("0.0001"))
        tx = tx_from_hex(minerador.getrawtransaction(txid))
        assert_equal(len(tx.vin), 2)
        assert_equal(len(tx.wit.vtxinwit[0].scriptWitness.stack[1]), 1952)
        assert_equal(tx.wit.vtxinwit[1].scriptWitness.stack[1], bytes(1))
        [bloco] = self.generatetoaddress(minerador, 1, endereco, sync_fun=self.no_op)
        assert txid in minerador.getblock(bloco)["tx"]


if __name__ == "__main__":
    Real26Refs(__file__).main()
