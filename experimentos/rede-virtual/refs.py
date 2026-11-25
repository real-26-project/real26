# Distribuído sob a licença MIT. Consulte COPYING.
"""Mede blocos ML-DSA-65 com referências no consenso experimental."""
from copy import deepcopy
from hashlib import sha256
import json
import subprocess
import time

from carga import VALOR_UTXO, transacao
from convidado import PASTA, RPC, aguardar
from frio import bloco_novo, enviar_bloco, trafego
from test_framework.blocktools import create_coinbase
from test_framework.messages import COIN, COutPoint, CTxIn, CTxOut, ser_vector, tx_from_hex


TRANSACOES = 555
DUPLAS = 139
ENTRADAS = TRANSACOES + DUPLAS
TAXA = 10_000
RODADAS = 3
GENESE = "3259f716dc16d1f59dd6b05a245a5ac268a1c8bc788e3304878bc0a0bc873405"
PORTA_RPC = 29773


def medir_refs(minerador):
    receptor = RPC("192.168.76.2", porta=PORTA_RPC)
    for no in (minerador, receptor):
        if aguardar(lambda: no("getblockhash", 0)) != GENESE:
            raise RuntimeError("Gênese inesperado.")
    minerador("addnode", "192.168.76.2:29774", "onetry")
    aguardar(lambda: any(par.get("version", 0) for par in receptor("getpeerinfo")))

    assinador = PASTA / "real26_mldsa65_sign_test"
    chaves = subprocess.check_output([assinador, "gerar"])
    origem = b"\x52\x20" + sha256(chaves[:1952]).digest()
    destino = b"\x52\x20" + sha256(subprocess.check_output([assinador, "gerar"])[:1952]).digest()
    descritor = minerador("getdescriptorinfo", f"raw({origem.hex()})")["descriptor"]
    anterior = CTxOut(VALOR_UTXO, origem)
    fontes = []
    for altura in range(1, RODADAS + 1):
        coinbase = create_coinbase(altura)
        coinbase.vout = [anterior for _ in range(ENTRADAS)]
        coinbase.vout.append(CTxOut(50 * COIN - ENTRADAS * VALOR_UTXO, origem))
        enviar_bloco(minerador, bloco_novo(minerador, coinbase, altura).serialize())
        fontes.append(coinbase.txid_int)

    ponta = minerador("generatetodescriptor", 103, descritor)[-1]
    aguardar(lambda: receptor("getbestblockhash") == ponta, intervalo=0.05)
    amostras = []
    for rodada, fonte in enumerate(fontes):
        transacoes = []
        for i in range(TRANSACOES):
            quantidade = 2 if i < DUPLAS else 1
            tx = transacao(COutPoint(fonte, i), [
                CTxOut(400_000, destino), CTxOut(quantidade * VALOR_UTXO - 400_000 - TAXA, origem),
            ])
            if quantidade == 2:
                tx.vin.append(CTxIn(COutPoint(fonte, TRANSACOES + i)))
            dados = chaves + tx.serialize_without_witness() + ser_vector([anterior] * quantidade)
            assinada = tx_from_hex(subprocess.check_output([assinador, "assinar-tx-refs"], input=dados).hex())
            if quantidade == 2 and assinada.wit.vtxinwit[1].scriptWitness.stack[1] != bytes(1):
                raise RuntimeError("A assinatura de laboratório não emitiu a referência canônica.")
            transacoes.append(assinada)

        altura = minerador("getblockcount") + 1
        coinbase = create_coinbase(altura, script_pubkey=origem, fees=TAXA * TRANSACOES)
        if rodada == 0:
            verificar_referencias(minerador, receptor, transacoes[0], altura, origem)
        bloco = bloco_novo(minerador, coinbase, altura, transacoes)
        dados = bloco.serialize()
        peso = bloco.get_weight()
        if not 3_700_000 <= peso <= 4_000_000 or receptor("getmempoolinfo")["size"]:
            raise RuntimeError("Peso inesperado ou mempool receptora ocupada.")
        antes = trafego(receptor)
        inicio = time.perf_counter()
        enviar_bloco(minerador, dados)
        local = time.perf_counter()
        aguardar(lambda: receptor("getbestblockhash") == bloco.hash_hex, limite=120, intervalo=0.025)
        aceito = time.perf_counter()
        depois = trafego(receptor)
        if receptor("getblockheader", bloco.hash_hex)["nTx"] != TRANSACOES + 1:
            raise RuntimeError("O nó receptor aceitou um bloco diferente do previsto.")
        amostra = {
            "referencias": True, "peso": peso, "bytes": len(dados),
            "local_s": round(local - inicio, 3), "par_s": round(aceito - inicio, 3),
            "apos_local_s": round(aceito - local, 3),
            "p2p": {k: depois.get(k, 0) - antes.get(k, 0) for k in ("block", "cmpctblock", "blocktxn")},
        }
        amostras.append(amostra)
        print("Bloco confirmado:", amostra, flush=True)
    print("REAL26_RESULTADO:" + json.dumps(amostras), flush=True)


def verificar_referencias(minerador, receptor, valido, altura, origem):
    if not minerador("testmempoolaccept", [valido.serialize().hex()])[0]["allowed"]:
        raise RuntimeError("A política do laboratório recusou a referência válida.")
    casos = [(0, b"\x01"), (1, b"\x01"), (1, b"\xff")]
    for entrada, referencia in casos:
        invalido = deepcopy(valido)
        invalido.wit.vtxinwit[entrada].scriptWitness.stack[1] = referencia
        verificar_rejeicao(minerador, receptor, invalido, altura, origem)
    adulterado = deepcopy(valido)
    pilha = adulterado.wit.vtxinwit[1].scriptWitness.stack
    pilha[0] = bytes([pilha[0][0] ^ 1]) + pilha[0][1:]
    verificar_rejeicao(minerador, receptor, adulterado, altura, origem)
    print("Referências futuras, próprias e fora do intervalo e assinatura adulterada rejeitadas.", flush=True)


def verificar_rejeicao(minerador, receptor, invalido, altura, origem):
    if minerador("testmempoolaccept", [invalido.serialize().hex()])[0]["allowed"]:
        raise RuntimeError("A mempool aceitou uma testemunha inválida.")
    coinbase = create_coinbase(altura, script_pubkey=origem, fees=TAXA)
    bloco = bloco_novo(minerador, coinbase, altura, [invalido])
    motivo = receptor("submitblock", bloco.serialize().hex())
    if not motivo or not motivo.startswith("block-script-verify-flag-failed"):
        raise RuntimeError(f"Resultado inesperado do consenso: {motivo}")
