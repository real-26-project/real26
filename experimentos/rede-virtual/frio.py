# Distribuído sob a licença MIT. Consulte COPYING.
"""Mede a transferência de blocos ML-DSA-65 para um nó sem mempool."""
import hashlib
import json
import statistics
import subprocess
import time

from carga import VALOR_UTXO, assinar, transacao
from convidado import GENESE, PASTA, RPC, aguardar
from test_framework.blocktools import add_witness_commitment, create_block, create_coinbase
from test_framework.messages import COIN, COutPoint, CTxOut, tx_from_hex


CENARIOS = (
    (4_000_000, 685), (10_000_000, 1710), (15_000_000, 2570),
    (10_000_000, 1710), (15_000_000, 2570), (4_000_000, 685),
    (15_000_000, 2570), (4_000_000, 685), (10_000_000, 1710),
)


def bloco_novo(no, coinbase, altura, transacoes=()):
    pai = no("getbestblockhash")
    mediana = no("getblockheader", pai)["mediantime"]
    bloco = create_block(
        hashprev=int(pai, 16), height=altura, ntime=max(int(time.time()), mediana + 1),
        coinbase=coinbase, txlist=list(transacoes),
    )
    if transacoes:
        add_witness_commitment(bloco)
    bloco.solve()
    return bloco


def enviar_bloco(no, dados):
    resposta = no("submitblock", dados.hex())
    if resposta is not None:
        raise RuntimeError(f"Bloco recusado pelo minerador: {resposta}")


def trafego(no):
    resultado = {}
    for par in no("getpeerinfo"):
        for nome, tamanho in par["bytesrecv_per_msg"].items():
            resultado[nome] = resultado.get(nome, 0) + tamanho
    return resultado


def medir_frio(minerador):
    receptor = RPC("192.168.76.2", porta=29753)
    for no in (minerador, receptor):
        if aguardar(lambda: no("getblockhash", 0)) != GENESE:
            raise RuntimeError("Gênese inesperado.")
    minerador("addnode", "192.168.76.2:29754", "onetry")
    aguardar(lambda: any(par.get("version", 0) for par in receptor("getpeerinfo")))

    assinador = PASTA / "real26_mldsa65_sign_test"
    chaves = subprocess.check_output([assinador, "gerar"])
    if len(chaves) != 1952 + 4032:
        raise RuntimeError("Par de chaves de tamanho inesperado.")
    origem = b"\x52\x20" + hashlib.sha256(chaves[:1952]).digest()
    destino = b"\x52\x20" + hashlib.sha256(subprocess.check_output([assinador, "gerar"])[:1952]).digest()
    desc = minerador("getdescriptorinfo", f"raw({origem.hex()})")["descriptor"]

    fontes = []
    for altura, (_, numero) in enumerate(CENARIOS, 1):
        coinbase = create_coinbase(altura)
        coinbase.vout = [CTxOut(VALOR_UTXO, origem) for _ in range(numero)]
        coinbase.vout.append(CTxOut(50 * COIN - VALOR_UTXO * numero, origem))
        bloco = bloco_novo(minerador, coinbase, altura)
        enviar_bloco(minerador, bloco.serialize())
        fontes.append(coinbase.txid_int)
    ponta = minerador("generatetodescriptor", 100, desc)[-1]
    aguardar(lambda: receptor("getbestblockhash") == ponta, intervalo=0.05)

    rtt = []
    for _ in range(9):
        inicio = time.perf_counter()
        receptor("getblockcount")
        rtt.append(1000 * (time.perf_counter() - inicio))
    print(f"RPC leve entre VMs: {statistics.median(rtt):.2f} ms.", flush=True)

    anterior = CTxOut(VALOR_UTXO, origem)
    resultados = []
    for (alvo, quantidade), fonte in zip(CENARIOS, fontes):
        altura = minerador("getblockcount") + 1
        inicio = time.perf_counter()
        pagamentos = [
            tx_from_hex(assinar(assinador, chaves, transacao(COutPoint(fonte, i), [
                CTxOut(400_000, destino), CTxOut(590_000, origem),
            ]), anterior))
            for i in range(quantidade)
        ]
        assinado = time.perf_counter()
        coinbase = create_coinbase(altura, script_pubkey=origem, fees=10_000 * quantidade)
        bloco = bloco_novo(minerador, coinbase, altura, pagamentos)
        dados = bloco.serialize()
        peso = 3 * len(bloco.serialize(with_witness=False)) + len(dados)
        if not 0.98 * alvo <= peso <= alvo:
            raise RuntimeError(f"Peso inesperado: {peso} para o alvo {alvo}.")
        if receptor("getmempoolinfo")["size"] != 0:
            raise RuntimeError("A mempool do receptor tem transações antes do bloco.")
        antes = trafego(receptor)
        inicio_envio = time.perf_counter()
        enviar_bloco(minerador, dados)
        aceito_local = time.perf_counter()
        aguardar(lambda: receptor("getbestblockhash") == bloco.hash_hex, limite=120, intervalo=0.025)
        confirmado = time.perf_counter()
        depois = trafego(receptor)
        cabecalho = receptor("getblockheader", bloco.hash_hex)
        if cabecalho["nTx"] != quantidade + 1:
            raise RuntimeError("O nó receptor confirmou um número inesperado de transações.")
        transferencia = {k: depois.get(k, 0) - antes.get(k, 0)
                         for k in ("block", "cmpctblock", "blocktxn")}
        if sum(transferencia.values()) < 0.95 * len(dados):
            raise RuntimeError("O tráfego medido para o receptor ficou abaixo do tamanho esperado.")
        amostra = {
            "altura": altura, "alvo": alvo, "pagamentos": quantidade, "peso": peso,
            "bytes": len(dados), "assinatura_s": round(assinado - inicio, 3),
            "aceitacao_local_s": round(aceito_local - inicio_envio, 3),
            "ate_confirmar_no_par_s": round(confirmado - inicio_envio, 3),
            "apos_aceitacao_local_s": round(confirmado - aceito_local, 3),
            "p2p_recebido_por_mensagem": transferencia,
        }
        resultados.append(amostra)
        print("Bloco confirmado com mempool vazia:", amostra, flush=True)

    print("REAL26_RESULTADO:" + json.dumps({
        "rtt_rpc_mediano_ms": round(statistics.median(rtt), 2), "blocos": resultados,
    }), flush=True)
