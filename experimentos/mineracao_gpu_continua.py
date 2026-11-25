# Distribuído sob a licença MIT. Consulte COPYING.
"""Exercita a mineração GPU e a retomada do nó validador da rede privada."""
from argparse import ArgumentParser
from contextlib import ExitStack
import json
from statistics import median
from time import perf_counter, sleep, time

from mineracao_gpu import GENESE, GPU, LOTE, aguardar, conferir_busca, criar_carteira, no_privado
from test_framework.blocktools import add_witness_commitment, create_block, create_coinbase
from test_framework.messages import COIN, tx_from_hex, uint256_from_compact


BITS_BUSCA = 0x1C10E331
ALVO = uint256_from_compact(BITS_BUSCA)
PORTA_MINERADOR = 29792
CARTEIRA_MINERADOR = "continua-gpu"
CARTEIRA_RECEPTOR = "continua-receptor"


def conectar(minerador, receptor):
    receptor("addnode", f"127.0.0.1:{PORTA_MINERADOR}", "onetry")
    aguardar(lambda: any(par["version"] for par in receptor("getpeerinfo")))
    aguardar(lambda: receptor("getbestblockhash") == minerador("getbestblockhash"))


def preparar_modelo(minerador, receptor, premio, destinatario, valor):
    txid = minerador("sendreal26", destinatario, valor, "0.0001", carteira=CARTEIRA_MINERADOR)
    aguardar(lambda: txid in receptor("getrawmempool"))
    modelo = minerador("getblocktemplate", json.dumps({"rules": ["segwit"]}))
    transacoes = [tx_from_hex(entrada["data"]) for entrada in modelo["transactions"]]
    assert [tx.txid_hex for tx in transacoes] == [txid]
    subsidio = 25 * COIN
    coinbase = create_coinbase(modelo["height"], script_pubkey=premio, nValue=25,
                               fees=modelo["coinbasevalue"] - subsidio, halving_period=420_000)
    bloco = create_block(tmpl=modelo, coinbase=coinbase, txlist=transacoes)
    add_witness_commitment(bloco)
    assert bytes(coinbase.vout[-1].scriptPubKey).hex() == modelo["default_witness_commitment"]
    return txid, bloco


def ensaiar(gpu, duracao, pausa):
    with no_privado(porta_rpc=29791, porta_p2p=PORTA_MINERADOR) as (minerador, pasta_m), ExitStack() as ciclo:
        receptor, pasta_r = ciclo.enter_context(no_privado(29795))
        assert minerador("getbestblockhash") == receptor("getbestblockhash") == GENESE
        conectar(minerador, receptor)
        remetente = criar_carteira(minerador, CARTEIRA_MINERADOR, desbloqueio=duracao + 300)
        destinatario = criar_carteira(receptor, CARTEIRA_RECEPTOR)
        maturacao = minerador("generatetoaddress", 112, remetente, 8_000_000)
        assert len(maturacao) == 112
        aguardar(lambda: receptor("getbestblockhash") == maturacao[-1])
        premio = bytes.fromhex(minerador("validateaddress", remetente)["scriptPubKey"])
        txid, bloco = preparar_modelo(minerador, receptor, premio, destinatario, "37.5")

        inicio = perf_counter()
        fim = inicio + duracao
        pausar_em = inicio + duracao / 2
        batimento = inicio + 60
        aceitos = []
        total = 0
        segundos_busca = 0.0
        nonce_inicial = 0
        reinicio_s = None
        gpu.preparar_busca(bloco.serialize()[:80])
        print(f"ENSAIO_INICIADO: {duracao} s; minerador {pasta_m}; receptor {pasta_r}", flush=True)
        while perf_counter() < fim:
            agora = perf_counter()
            if reinicio_s is None and agora >= pausar_em:
                ponta = receptor("getbestblockhash")
                inicio_pausa = perf_counter()
                print("PAUSA: GPU pausada; reiniciando receptor.", flush=True)
                ciclo.close()
                receptor, _ = ciclo.enter_context(no_privado(29795, pasta=pasta_r))
                assert receptor("getbestblockhash") == ponta
                if CARTEIRA_RECEPTOR not in receptor("listwallets"):
                    receptor("loadwallet", CARTEIRA_RECEPTOR)
                conectar(minerador, receptor)
                sleep(max(0, pausa - (perf_counter() - inicio_pausa)))
                reinicio_s = perf_counter() - inicio_pausa
                print(f"RETOMADA: receptor sincronizado; pausa de {reinicio_s:.2f} s.", flush=True)
                continue
            if agora >= batimento:
                taxa = total / segundos_busca / 1e6 if segundos_busca else 0
                print(f"PROGRESSO: {(agora - inicio) / 60:.1f} min; {len(aceitos)} blocos; {taxa:.2f} MH/s.", flush=True)
                batimento += 60

            inicio_lote = perf_counter()
            nonce = gpu.procurar(nonce_inicial)
            segundos_busca += perf_counter() - inicio_lote
            total += LOTE
            nonce_inicial += LOTE
            if nonce is not None:
                bloco.nNonce = nonce
                if bloco.hash_int <= ALVO and bloco.is_valid():
                    submissao = perf_counter()
                    resposta = minerador("submitblock", bloco.serialize().hex())
                    if resposta is not None:
                        raise RuntimeError(f"Bloco recusado: {resposta}")
                    aguardar(lambda: receptor("getbestblockhash") == bloco.hash_hex)
                    recebido = perf_counter()
                    info = receptor("gettransaction", txid, carteira=CARTEIRA_RECEPTOR)
                    assert info["confirmations"] == 1
                    aceitos.append({
                        "hash": bloco.hash_hex, "txid": txid, "valor": info["amount"],
                        "tempo_desde_inicio_s": round(recebido - inicio, 3),
                        "submissao_ate_par_s": round(recebido - submissao, 3),
                        "apos_reinicio": reinicio_s is not None,
                    })
                    print("BLOCO_ACEITO:" + json.dumps(aceitos[-1]), flush=True)
                    if perf_counter() >= fim:
                        break
                    txid, bloco = preparar_modelo(minerador, receptor, premio, destinatario, "1")
                    nonce_inicial = 0
                    gpu.preparar_busca(bloco.serialize()[:80])
                    continue

            if nonce_inicial == 1 << 32:
                bloco.nTime = max(int(time()), bloco.nTime + 1)
                nonce_inicial = 0
                gpu.preparar_busca(bloco.serialize()[:80])

        assert reinicio_s is not None
        assert minerador("getbestblockhash") == receptor("getbestblockhash")
        duracao_real = perf_counter() - inicio
        intervalos = [
            b["tempo_desde_inicio_s"] - a["tempo_desde_inicio_s"]
            for a, b in zip(aceitos, aceitos[1:])
        ]
        print("REAL26_RESULTADO:" + json.dumps({
            "duracao_s": round(duracao_real, 3), "nBits_busca": f"0x{BITS_BUSCA:08x}",
            "pausa_s": round(reinicio_s, 3), "segundos_busca": round(segundos_busca, 3),
            "hashes": total, "MH_s": round(total / segundos_busca / 1e6, 3),
            "mediana_intervalo_s": round(median(intervalos), 3) if intervalos else None,
            "mediana_submissao_ate_par_s": round(median(b["submissao_ate_par_s"] for b in aceitos), 3) if aceitos else None,
            "blocos": aceitos, "dados_minerador": pasta_m, "dados_receptor": pasta_r,
        }), flush=True)
        if not any(b["apos_reinicio"] for b in aceitos):
            raise RuntimeError("O ensaio terminou sem um bloco encontrado após a retomada.")


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--minutos", type=int, default=30)
    args = parser.parse_args()
    if not 30 <= args.minutos <= 60:
        parser.error("Escolha entre 30 e 60 minutos.")
    with GPU() as gpu:
        gpu.validar()
        conferir_busca(gpu)
        ensaiar(gpu, args.minutos * 60, pausa=15)


if __name__ == "__main__":
    main()
