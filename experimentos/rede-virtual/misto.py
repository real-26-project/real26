# Distribuído sob a licença MIT. Consulte COPYING.
"""Compara a mesma carga mista com e sem transações na mempool do receptor."""
import hashlib
import json
import subprocess
import time

from carga import LIMITE, VALOR_UTXO, assinar, transacao
from convidado import GENESE, PASTA, RPC, aguardar
from frio import bloco_novo, enviar_bloco, trafego
from test_framework.blocktools import create_coinbase
from test_framework.messages import COIN, COutPoint, CTxOut, tx_from_hex


DESTINATARIOS = 10
CENARIOS = {
    "misto": (302, 302, (0, 100, 100, 0, 0, 100)),
    "misto80": (520, 130, (0, 50, 100, 100, 50, 0)),
}
TAXA = 10_000


def medir_misto(minerador, modo="misto"):
    individuais, lotes, condicoes = CENARIOS[modo]
    quantidade = individuais + lotes
    pagamentos = individuais + lotes * DESTINATARIOS
    receptor = RPC("192.168.76.2")
    for no in (minerador, receptor):
        if aguardar(lambda: no("getblockhash", 0)) != GENESE:
            raise RuntimeError("Gênese inesperado.")
    receptor("addnode", "192.168.76.1:29744", "onetry")
    aguardar(lambda: any(par.get("version", 0) for par in receptor("getpeerinfo")))

    assinador = PASTA / "real26_mldsa65_sign_test"
    chave = subprocess.check_output([assinador, "gerar"])
    origem = b"\x52\x20" + hashlib.sha256(chave[:1952]).digest()
    destinos = [
        b"\x52\x20" + hashlib.sha256(subprocess.check_output([assinador, "gerar"])[:1952]).digest()
        for _ in range(DESTINATARIOS)
    ]
    descritor = minerador("getdescriptorinfo", f"raw({origem.hex()})")["descriptor"]
    fontes = []
    for altura in range(1, len(condicoes) + 1):
        coinbase = create_coinbase(altura)
        coinbase.vout = [CTxOut(VALOR_UTXO, origem) for _ in range(quantidade)]
        coinbase.vout.append(CTxOut(50 * COIN - quantidade * VALOR_UTXO, origem))
        enviar_bloco(minerador, bloco_novo(minerador, coinbase, altura).serialize())
        fontes.append(coinbase.txid_int)
    ponta = minerador("generatetodescriptor", 104, descritor)[-1]
    aguardar(lambda: receptor("getbestblockhash") == ponta, intervalo=0.05)

    resultados = []
    anterior = CTxOut(VALOR_UTXO, origem)
    for fonte, cobertura in zip(fontes, condicoes):
        if any(no("getmempoolinfo")["size"] for no in (minerador, receptor)):
            raise RuntimeError("A rodada precisa começar com as duas mempools vazias.")
        hexs = []
        for indice in range(quantidade):
            scripts = destinos[:1] if indice < individuais else destinos
            saidas = [CTxOut(40_000, script) for script in scripts]
            saidas.append(CTxOut(VALOR_UTXO - 40_000 * len(scripts) - TAXA, origem))
            hexs.append(assinar(assinador, chave, transacao(COutPoint(fonte, indice), saidas), anterior))
        transacoes = [tx_from_hex(dados) for dados in hexs]
        altura = minerador("getblockcount") + 1
        coinbase = create_coinbase(altura, script_pubkey=origem, fees=TAXA * quantidade)
        bloco = bloco_novo(minerador, coinbase, altura, transacoes)
        dados = bloco.serialize()
        peso = 3 * len(bloco.serialize(with_witness=False)) + len(dados)
        if not 0.99 * LIMITE <= peso <= LIMITE:
            raise RuntimeError(f"Peso do cenário misto fora do intervalo: {peso}.")

        preparo = 0
        # Seleciona a mesma fração de transações individuais e de lotes.
        selecionadas = list(range(individuais * cobertura // 100))
        selecionadas += range(individuais, individuais + lotes * cobertura // 100)
        if selecionadas:
            inicio_preparo = time.perf_counter()
            for inicio in range(0, len(selecionadas), 40):
                minerador.lote("sendrawtransaction", [[hexs[i]] for i in selecionadas[inicio:inicio + 40]])
            txids = {transacoes[i].txid_hex for i in selecionadas}
            aguardar(lambda: set(receptor("getrawmempool")) == txids, limite=150, intervalo=0.5)
            preparo = time.perf_counter() - inicio_preparo
        presentes = receptor("getmempoolinfo")["size"]
        if presentes != len(selecionadas):
            raise RuntimeError(f"Tamanho inesperado da mempool receptora: {presentes}.")

        antes = trafego(receptor)
        inicio_envio = time.perf_counter()
        enviar_bloco(minerador, dados)
        aceito_local = time.perf_counter()
        aguardar(lambda: receptor("getbestblockhash") == bloco.hash_hex, limite=120, intervalo=0.025)
        aceito_par = time.perf_counter()
        depois = trafego(receptor)
        if receptor("getblockheader", bloco.hash_hex)["nTx"] != quantidade + 1:
            raise RuntimeError("O bloco confirmado ficou incompleto.")
        amostra = {
            "altura": altura, "cobertura_pct": cobertura, "mempool": presentes,
            "transacoes": quantidade, "pagamentos": pagamentos,
            "peso": peso, "bytes_bloco": len(dados),
            "preparo_mempool_s": round(preparo, 3),
            "submissao_ate_par_s": round(aceito_par - inicio_envio, 3),
            "local_ate_par_s": round(aceito_par - aceito_local, 3),
            "p2p": {k: depois.get(k, 0) - antes.get(k, 0) for k in ("block", "cmpctblock", "blocktxn")},
        }
        resultados.append(amostra)
        print("Bloco misto confirmado:", amostra, flush=True)
    print("REAL26_RESULTADO:" + json.dumps(resultados), flush=True)
