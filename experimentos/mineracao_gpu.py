# Distribuído sob a licença MIT. Consulte COPYING.
"""Minera três blocos de teste com a Radeon e os submete ao nó privado."""
from argparse import ArgumentParser
from contextlib import contextmanager
import json
import struct
import subprocess
from time import perf_counter, sleep, time

from benchmark_pow_gpu import GPU, LOTE
from test_framework.blocktools import add_witness_commitment, create_block, create_coinbase
from test_framework.messages import COIN, tx_from_hex, uint256_from_compact


WSL = ["wsl", "-d", "REAL26-Dev", "-u", "root", "--"]
BINARIOS = "/opt/real26/build/bin"
GENESE = "0007326bf77a1489a5e6ee7aa98affe5baac14aa7f2b694a86e2b54c8ae24733"
ALVO_HISTORICO = uint256_from_compact(0x1d00ffff)


@contextmanager
def no_privado(porta_rpc=29793, porta_p2p=None, pasta=None):
    if pasta is None:
        pasta = subprocess.check_output([*WSL, "mktemp", "-d", "/tmp/real26-gpu.XXXXXXXX"], text=True).strip()
    rede = [
        "-testnet4", "-real26test", "-real26testrefs", "-real26ensaio",
        f"-datadir={pasta}", f"-rpcport={porta_rpc}",
    ]
    escuta = ["-listen=0"] if porta_p2p is None else ["-listen=1", f"-bind=127.0.0.1:{porta_p2p}"]
    subprocess.run([
        *WSL, BINARIOS + "/bitcoind", *rede, *escuta,
        "-connect=0", "-listenonion=0", "-discover=0", "-daemonwait",
    ], check=True)

    def rpc(metodo, *args, carteira=None):
        opcoes = [] if carteira is None else [f"-rpcwallet={carteira}"]
        pedido = [*WSL, BINARIOS + "/bitcoin-cli", *rede, *opcoes, metodo, *map(str, args)]
        saida = subprocess.check_output(pedido, text=True).strip()
        if not saida:
            return None
        try:
            return json.loads(saida)
        except json.JSONDecodeError:
            return saida

    try:
        yield rpc, pasta
    finally:
        rpc("stop")
        pid = f"{pasta}/real26ensaio/bitcoind.pid"
        aguardar(lambda: subprocess.run([*WSL, "test", "!", "-e", pid], check=False).returncode == 0)


def conferir_busca(gpu):
    raiz = bytes.fromhex("4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b")
    cabecalho = struct.pack("<I", 1) + bytes(32) + raiz[::-1] + struct.pack("<III", 1231006505, 0x1d00ffff, 0)
    gpu.preparar_busca(cabecalho)
    assert gpu.procurar(2083236793) == 2083236893


def minerar(gpu, bloco, limite=180):
    inicio = perf_counter()
    total = 0
    while perf_counter() - inicio < limite:
        gpu.preparar_busca(bloco.serialize()[:80])
        for primeiro in range(0, 1 << 32, LOTE):
            nonce = gpu.procurar(primeiro)
            total += LOTE
            if nonce is not None:
                bloco.nNonce = nonce
                if bloco.hash_int <= ALVO_HISTORICO and bloco.is_valid():
                    return total, perf_counter() - inicio
            if perf_counter() - inicio >= limite:
                break
        # Se esgotar a faixa de nonce, muda o horário e inicia outro cabeçalho.
        bloco.nTime = max(bloco.nTime + 1, int(time()))
    raise RuntimeError("A GPU não encontrou uma solução no tempo do ensaio.")


def criar_carteira(rpc, nome, desbloqueio=300):
    senha = "senha descartavel de ensaio"
    rpc("createwallet", nome, "false", "false", senha)
    rpc("walletpassphrase", senha, desbloqueio, carteira=nome)
    return rpc("getreal26address", carteira=nome)


def aguardar(condicao, limite=90):
    fim = perf_counter() + limite
    while perf_counter() < fim:
        if condicao():
            return
        sleep(0.2)
    raise RuntimeError("Tempo de sincronização excedido.")


def testar_modelo_com_pagamento(gpu):
    with no_privado(porta_rpc=29791, porta_p2p=29792) as (minerador, pasta_m), no_privado(29795) as (receptor, pasta_r):
        for no in (minerador, receptor):
            assert no("getbestblockhash") == GENESE
        receptor("addnode", "127.0.0.1:29792", "onetry")
        aguardar(lambda: any(par["version"] for par in minerador("getpeerinfo")))
        remetente = criar_carteira(minerador, "mineracao-gpu")
        destinatario = criar_carteira(receptor, "recebimento-gpu")

        recompensas = minerador("generatetoaddress", 102, remetente, 4_000_000)
        assert len(recompensas) == 102
        aguardar(lambda: receptor("getbestblockhash") == recompensas[-1])
        txid = minerador("sendreal26", destinatario, "37.5", "0.0001", carteira="mineracao-gpu")
        aguardar(lambda: txid in receptor("getrawmempool"))
        tx = tx_from_hex(receptor("getrawtransaction", txid))
        assert len(tx.vin) == 2 and tx.wit.vtxinwit[1].scriptWitness.stack[1] == bytes(1)

        modelo = minerador("getblocktemplate", json.dumps({"rules": ["segwit"]}))
        assert [entrada["txid"] for entrada in modelo["transactions"]] == [txid]
        premio = bytes.fromhex(minerador("validateaddress", remetente)["scriptPubKey"])
        subsidio = 25 * COIN
        taxas = modelo["coinbasevalue"] - subsidio
        coinbase = create_coinbase(modelo["height"], script_pubkey=premio, nValue=25,
                                   fees=taxas, halving_period=420_000)
        bloco = create_block(tmpl=modelo, coinbase=coinbase, txlist=[tx])
        add_witness_commitment(bloco)
        assert bytes(coinbase.vout[-1].scriptPubKey).hex() == modelo["default_witness_commitment"]
        print("Modelo de bloco recebido com pagamento ML-DSA-65 de duas entradas.", flush=True)

        hashes, segundos = minerar(gpu, bloco)
        inicio_submissao = perf_counter()
        resposta = minerador("submitblock", bloco.serialize().hex())
        if resposta is not None:
            raise RuntimeError(f"O nó minerador recusou o bloco: {resposta}.")
        aguardar(lambda: receptor("getbestblockhash") == bloco.hash_hex)
        propagacao = perf_counter() - inicio_submissao
        confirmado = receptor("gettransaction", txid, carteira="recebimento-gpu")
        assert confirmado["confirmations"] == 1 and confirmado["amount"] == 37.5
        assert receptor("getblock", bloco.hash_hex)["tx"][-1] == txid
        print("REAL26_RESULTADO:" + json.dumps({
            "altura": modelo["height"], "hash": bloco.hash_hex, "txid": txid,
            "valor": confirmado["amount"], "confirmacoes": confirmado["confirmations"],
            "hashes": hashes, "segundos_busca": round(segundos, 3),
            "MH_s": round(hashes / segundos / 1e6, 3),
            "submissao_ate_par_s": round(propagacao, 3),
            "dados_minerador": pasta_m, "dados_receptor": pasta_r,
        }), flush=True)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--blocos", type=int, default=3)
    parser.add_argument("--pagamento", action="store_true", help="Minera um bloco de modelo RPC com pagamento e um par.")
    args = parser.parse_args()
    if not 1 <= args.blocos <= 10:
        parser.error("Escolha de 1 a 10 blocos.")
    if args.pagamento:
        with GPU() as gpu:
            gpu.validar()
            conferir_busca(gpu)
            testar_modelo_com_pagamento(gpu)
        return
    with GPU() as gpu, no_privado() as (rpc, pasta):
        gpu.validar()
        conferir_busca(gpu)
        assert rpc("getbestblockhash") == GENESE
        print(f"Diretório isolado do nó: {pasta}", flush=True)
        endereco = criar_carteira(rpc, "mineracao-gpu")
        premio = bytes.fromhex(rpc("validateaddress", endereco)["scriptPubKey"])
        resultados = []
        for altura in range(1, args.blocos + 1):
            pai = rpc("getbestblockhash")
            cabecalho = rpc("getblockheader", pai)
            horario = max(int(time()), cabecalho["mediantime"] + 1)
            coinbase = create_coinbase(altura, script_pubkey=premio, nValue=25, halving_period=420_000)
            bloco = create_block(int(pai, 16), coinbase=coinbase, ntime=horario)
            bloco.nBits = int(cabecalho["bits"], 16)
            add_witness_commitment(bloco)
            hashes, segundos = minerar(gpu, bloco)
            resposta = rpc("submitblock", bloco.serialize().hex())
            if resposta is not None or rpc("getbestblockhash") != bloco.hash_hex:
                raise RuntimeError(f"O nó recusou o bloco {altura}: {resposta}.")
            aceito = rpc("getblock", bloco.hash_hex, 2)
            assert aceito["height"] == altura and aceito["tx"][0]["vout"][0]["value"] == 25
            resultado = {
                "altura": altura, "hash": bloco.hash_hex, "nonce": bloco.nNonce,
                "nBits_rede": f"0x{bloco.nBits:08x}", "hashes": hashes,
                "segundos": round(segundos, 3), "MH_s": round(hashes / segundos / 1e6, 3),
            }
            resultados.append(resultado)
            print(resultado, flush=True)
        print("REAL26_RESULTADO:" + json.dumps(resultados), flush=True)


if __name__ == "__main__":
    main()
