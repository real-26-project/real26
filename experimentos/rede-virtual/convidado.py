# Distribuído sob a licença MIT. Consulte COPYING.
"""Mede a confirmação em dois convidados REAL-26 ligados por Ethernet virtual."""
import base64
import http.client
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

PASTA = Path("/mnt/real26")
GENESE = "26df5874074ef2b195f095a7f38d13db0dbf22e11b4ab1b22d881303fc408905"
AUTH = base64.b64encode(b"teste-vm:credencial-temporaria-do-enlace-isolado").decode()


class RPC:
    def __init__(self, ip, carteira=None, *, porta=29743):
        self.conexao = http.client.HTTPConnection(ip, porta, timeout=90)
        self.rota = "/" if carteira is None else f"/wallet/{carteira}"

    def pedido(self, dados):
        try:
            self.conexao.request("POST", self.rota, json.dumps(dados), {
                "Authorization": "Basic " + AUTH, "Content-Type": "application/json",
            })
            return json.loads(self.conexao.getresponse().read())
        except (OSError, http.client.HTTPException):
            self.conexao.close()
            raise

    @staticmethod
    def resultado(resposta):
        if resposta.get("error") is not None:
            raise RuntimeError(resposta["error"]["message"])
        return resposta["result"]

    def __call__(self, metodo, *params):
        return self.resultado(self.pedido({
            "jsonrpc": "2.0", "id": 1, "method": metodo, "params": params,
        }))

    def lote(self, metodo, parametros):
        respostas = self.pedido([
            {"jsonrpc": "2.0", "id": i, "method": metodo, "params": params}
            for i, params in enumerate(parametros)
        ])
        por_id = {resposta["id"]: self.resultado(resposta) for resposta in respostas}
        return [por_id[i] for i in range(len(parametros))]


def aguardar(funcao, limite=90, intervalo=0.005):
    inicio = time.monotonic()
    erro = None
    while time.monotonic() - inicio < limite:
        try:
            resultado = funcao()
            if resultado:
                return resultado
        except (OSError, RuntimeError, http.client.HTTPException) as atual:
            erro = atual
        time.sleep(intervalo)
    raise RuntimeError(f"Tempo de espera excedido: {erro}")


def iniciar(numero, modo):
    dados = Path("/var/lib/real26-test")
    dados.mkdir(mode=0o700, exist_ok=True)
    ip = f"192.168.76.{numero}"
    adicional = ["-blocksonly=1"] if modo in ("frio", "refs") and numero == 2 else []
    if modo == "refs":
        adicional.append("-real26refs")
    subprocess.run([
        PASTA / "bitcoind", "-regtest", "-real26dev", f"-datadir={dados}",
        "-bind=" + ip, "-rpcbind=" + ip, "-rpcallowip=192.168.76.0/24",
        "-rpcuser=teste-vm", "-rpcpassword=credencial-temporaria-do-enlace-isolado",
        "-listen=1", "-connect=0", "-dnsseed=0", "-fixedseeds=0", "-discover=0",
        "-listenonion=0", "-dbcache=100", "-daemonwait", *adicional,
    ], check=True)
    return RPC(ip, porta={"frio": 29753, "refs": 29773}.get(modo, 29743))


def medir(receptor):
    minerador = RPC("192.168.76.1")
    for no in (minerador, receptor):
        if aguardar(lambda: no("getblockhash", 0)) != GENESE:
            raise RuntimeError("Gênese inesperado.")
    receptor("addnode", "192.168.76.1:29744", "onetry")
    aguardar(lambda: any(par.get("version", 0) for par in receptor("getpeerinfo")))

    senha = "carteira-temporaria-sem-valor"
    minerador("createwallet", "medicao", False, False, senha)
    carteira = RPC("192.168.76.1", "medicao")
    carteira("walletpassphrase", senha, 600)
    origem = carteira("getreal26address")
    destino = origem
    lotes = (1, 25, 100)
    rodadas = 3
    print("Preparando recompensas ML-DSA-65 para os lotes.", flush=True)
    minerador("generatetoaddress", sum(lotes) * rodadas, origem)
    ponta = minerador("generatetoaddress", 100, origem)[-1]
    aguardar(lambda: receptor("getbestblockhash") == ponta)
    resultados = []

    for tamanho in lotes:
        amostras = []
        for _ in range(rodadas):
            inicio = time.perf_counter()
            txids = [carteira("sendreal26", destino, 0.1, 0.0001) for _ in range(tamanho)]
            enviadas = time.perf_counter()
            aguardar(lambda: set(txids).issubset(receptor("getrawmempool")))
            preparadas = time.perf_counter()
            [bloco] = minerador("generatetoaddress", 1, origem)
            minerado = time.perf_counter()
            aguardar(lambda: receptor("getbestblockhash") == bloco)
            confirmado = time.perf_counter()
            confirmado_info = receptor("getblock", bloco)
            if not set(txids).issubset(confirmado_info["tx"]):
                raise RuntimeError("O bloco confirmado não contém todos os pagamentos.")
            amostras.append({
                "total_ms": 1000 * (confirmado - inicio),
                "envio_ms": 1000 * (enviadas - inicio),
                "mempool_ms": 1000 * (preparadas - enviadas),
                "inclusao_ms": 1000 * (confirmado - preparadas),
                "apos_rpc_minerador_ms": 1000 * (confirmado - minerado),
                "peso_bloco": confirmado_info["weight"],
                "bytes_bloco": confirmado_info["size"],
            })
        resultados.append({
            "pagamentos": tamanho, "rodadas": rodadas,
            **{campo: round(statistics.median(a[campo] for a in amostras), 2)
               for campo in amostras[0]},
        })
        print("Lote concluído:", resultados[-1], flush=True)
    print("REAL26_RESULTADO:" + json.dumps(resultados), flush=True)


if __name__ == "__main__":
    try:
        numero = int(sys.argv[1])
        modo = sys.argv[2] if len(sys.argv) > 2 else "local"
        no = iniciar(numero, modo)
        if numero == 1 and modo == "frio":
            from frio import medir_frio
            medir_frio(no)
        elif numero == 1 and modo == "refs":
            from refs import medir_refs
            medir_refs(no)
        elif numero == 1 and modo in ("misto", "misto80"):
            from misto import medir_misto
            medir_misto(no, modo)
        elif numero == 2 and modo == "carga":
            from carga import medir_carga
            medir_carga(no)
        elif numero == 2 and modo == "local":
            medir(no)
    except Exception as erro:
        print(f"REAL26_FALHA: {erro}", flush=True)
        raise
