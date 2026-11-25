# Distribuído sob a licença MIT. Consulte COPYING.
"""Mede três blocos ML-DSA-65 consecutivos de 680 pagamentos."""
import hashlib
import http.client
import json
import statistics
import subprocess
import time

from convidado import GENESE, PASTA, RPC, aguardar
from test_framework.messages import COIN, COutPoint, CTransaction, CTxIn, CTxOut, ser_vector


PAGAMENTOS = 680
BLOCOS = 3
VALOR_UTXO = COIN // 100
LIMITE = 4_000_000


def transacao(ponto, saidas):
    tx = CTransaction()
    tx.version = 2
    tx.vin = [CTxIn(ponto)]
    tx.vout = saidas
    return tx


def assinar(assinador, chave, tx, anterior):
    entrada = chave + tx.serialize_without_witness() + ser_vector([anterior])
    return subprocess.check_output([assinador, "assinar-tx"], input=entrada).hex()


def medir_carga(receptor):
    minerador = RPC("192.168.76.1")
    for no in (minerador, receptor):
        if aguardar(lambda: no("getblockhash", 0)) != GENESE:
            raise RuntimeError("Gênese inesperado.")
    receptor("addnode", "192.168.76.1:29744", "onetry")
    aguardar(lambda: any(par.get("version", 0) for par in receptor("getpeerinfo")))

    assinador = PASTA / "real26_mldsa65_sign_test"
    chaves = subprocess.check_output([assinador, "gerar"])
    if len(chaves) != 1952 + 4032:
        raise RuntimeError("Par de chaves de tamanho inesperado.")
    mldsa65 = b"\x52\x20" + hashlib.sha256(chaves[:1952]).digest()
    destino = b"\x52\x20" + hashlib.sha256(subprocess.check_output([assinador, "gerar"])[:1952]).digest()
    desc_mldsa65 = minerador("getdescriptorinfo", f"raw({mldsa65.hex()})")["descriptor"]
    blocos_fonte = minerador("generatetodescriptor", BLOCOS, desc_mldsa65)
    minerador("generatetodescriptor", 100, desc_mldsa65)

    lotes = []
    for bloco in blocos_fonte:
        fonte = minerador("getblock", bloco)["tx"][0]
        saidas = [CTxOut(VALOR_UTXO, mldsa65) for _ in range(PAGAMENTOS)]
        saidas.append(CTxOut(50 * COIN - PAGAMENTOS * VALOR_UTXO - 100_000, destino))
        tx = transacao(COutPoint(int(fonte, 16), 0), saidas)
        txid = minerador("sendrawtransaction", assinar(assinador, chaves, tx, CTxOut(50 * COIN, mldsa65)))
        lotes.append(int(txid, 16))
    [preparacao] = minerador("generatetodescriptor", 1, desc_mldsa65)
    aguardar(lambda: receptor("getbestblockhash") == preparacao)
    if receptor("getmempoolinfo")["size"] != 0:
        raise RuntimeError("A segunda mempool não começou vazia.")
    rtt = []
    for _ in range(9):
        inicio = time.perf_counter()
        minerador("getblockcount")
        rtt.append(1000 * (time.perf_counter() - inicio))
    print(f"RPC leve entre VMs: mediana {statistics.median(rtt):.2f} ms.", flush=True)

    amostras = []
    inicio_serie = time.perf_counter()
    for rodada, lote in enumerate(lotes, 1):
        inicio = time.perf_counter()
        dados = [
            assinar(assinador, chaves, transacao(COutPoint(lote, i), [
                CTxOut(400_000, destino), CTxOut(590_000, mldsa65),
            ]), CTxOut(VALOR_UTXO, mldsa65))
            for i in range(PAGAMENTOS)
        ]
        assinado = time.perf_counter()
        txids = set(minerador.lote("sendrawtransaction", [[tx] for tx in dados]))
        enviado = time.perf_counter()
        if len(txids) != PAGAMENTOS:
            raise RuntimeError("Número incorreto de transações submetidas.")
        print(f"Lote {rodada}: {PAGAMENTOS} pagamentos submetidos. Aguardando a segunda mempool.", flush=True)
        # Um lote pode ocupar o bloco mesmo se o par só tiver recebido parte da
        # mempool. O protocolo P2P deve solicitar os dados restantes do bloco.
        progresso = enviado
        presentes = 0
        receptor.conexao.close()
        receptor.conexao.timeout = 8
        while True:
            try:
                # A consulta leve evita serializar toda a mempool a cada sondagem.
                presentes = receptor("getmempoolinfo")["size"]
                if presentes == PAGAMENTOS:
                    break
            except (OSError, http.client.HTTPException):
                pass
            agora = time.perf_counter()
            if agora - enviado >= 30:
                break
            if agora - progresso >= 20:
                print(f"Lote {rodada}: {presentes}/{PAGAMENTOS} transações na segunda mempool.", flush=True)
                progresso = agora
            time.sleep(0.1)
        receptor.conexao.close()
        receptor.conexao.timeout = 90
        recebido = time.perf_counter()
        [bloco] = minerador("generatetodescriptor", 1, desc_mldsa65)
        aguardar(lambda: receptor("getbestblockhash") == bloco)
        confirmado = time.perf_counter()
        info = aguardar(lambda: receptor("getblock", bloco), limite=30)
        if receptor("getmempoolinfo")["size"] != 0:
            raise RuntimeError("Restaram transações na segunda mempool após a confirmação.")
        if not 0.95 * LIMITE <= info["weight"] <= LIMITE or not txids.issubset(info["tx"]):
            raise RuntimeError(f"O bloco {rodada} ficou incompleto: peso {info['weight']}.")
        amostra = {
            "altura": info["height"],
            "pagamentos": PAGAMENTOS,
            "peso": info["weight"],
            "bytes": info["size"],
            "assinatura_s": round(assinado - inicio, 3),
            "submissao_s": round(enviado - assinado, 3),
            "espera_mempool_s": round(recebido - enviado, 3),
            "no_par_antes_do_bloco": presentes,
            "mineracao_confirmacao_ms": round(1000 * (confirmado - recebido), 2),
            "total_s": round(confirmado - inicio, 3),
        }
        amostras.append(amostra)
        print("Bloco de carga confirmado:", amostra, flush=True)

    final = {
        "rtt_rpc_mediano_ms": round(statistics.median(rtt), 2),
        "tps_serie": round(PAGAMENTOS * BLOCOS / (time.perf_counter() - inicio_serie), 3),
        "blocos": amostras,
    }
    print("REAL26_RESULTADO:" + json.dumps(final), flush=True)
