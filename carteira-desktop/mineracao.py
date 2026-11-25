# Distribuído sob a licença MIT. Consulte COPYING.
"""Mineração SHA-256 duplo a partir dos modelos do nó local da carteira."""

from concurrent.futures import ProcessPoolExecutor
from contextlib import ExitStack
from hashlib import sha256
from pathlib import Path
from queue import SimpleQueue
import struct
import sys
from threading import Event, Thread
from time import perf_counter, time


LIMITE_NONCE = 1 << 32
LOTE_CPU = 2048


def buscar_cpu(cabecalho, alvo, inicio, quantidade):
    """Testa uma faixa de nonces em um processo independente do Tk."""
    digest = sha256(cabecalho[:76])
    for nonce in range(inicio, inicio + quantidade):
        primeiro = digest.copy()
        primeiro.update(struct.pack("<I", nonce))
        if int.from_bytes(sha256(primeiro.digest()).digest(), "little") <= alvo:
            return nonce, nonce - inicio + 1
    return None, quantidade


class Minerador:
    def __init__(self, no):
        self.no = no
        self.eventos = SimpleQueue()
        self.interromper = Event()
        self.continuar = Event()
        self.thread = None

    def iniciar(self, modo, trabalhadores):
        if self.thread is not None and self.thread.is_alive():
            return False
        self.interromper.clear()
        self.continuar.set()
        self.thread = Thread(target=self.executar, args=(modo, trabalhadores), name="real26-mineracao")
        self.thread.start()
        return True

    def pausar(self):
        self.continuar.clear()

    def retomar(self):
        self.continuar.set()

    def encerrar(self):
        self.interromper.set()
        self.continuar.set()

    def executar(self, modo, trabalhadores):
        try:
            self.minerar(modo, trabalhadores)
        except Exception as erro:
            self.eventos.put(("erro", str(erro).strip() or type(erro).__name__))
        finally:
            self.eventos.put(("encerrado", None))

    def minerar(self, modo, trabalhadores):
        raiz = Path(__file__).resolve().parents[1]
        for pasta in (raiz / "experimentos", raiz / "test/functional"):
            if str(pasta) not in sys.path:
                sys.path.insert(0, str(pasta))
        if modo != "cpu":
            from benchmark_pow_gpu import GPU, LOTE
            from mineracao_gpu import conferir_busca

            with ExitStack() as recursos:
                try:
                    gpu = recursos.enter_context(GPU())
                    gpu.validar()
                    conferir_busca(gpu)
                except (OSError, RuntimeError, AssertionError):
                    if modo == "gpu":
                        raise
                    self.eventos.put(("alternativa", None))
                else:

                    def lote_gpu(alvo, inicio):
                        return gpu.procurar(inicio, alvo >> 224), LOTE

                    self.buscar_blocos("GPU", LOTE, gpu.preparar_busca, lote_gpu)
                    return

        if self.interromper.is_set():
            return
        with ProcessPoolExecutor(max_workers=trabalhadores) as processos:
            cabecalho = b""

            def preparar(dados):
                nonlocal cabecalho
                cabecalho = dados

            def lote_cpu(alvo, inicio):
                fim = min(LIMITE_NONCE, inicio + LOTE_CPU * trabalhadores)
                tarefas = [
                    processos.submit(buscar_cpu, cabecalho, alvo, nonce, min(LOTE_CPU, fim - nonce))
                    for nonce in range(inicio, fim, LOTE_CPU)
                ]
                resultados = [tarefa.result() for tarefa in tarefas]
                solucoes = [nonce for nonce, _ in resultados if nonce is not None]
                return min(solucoes, default=None), sum(total for _, total in resultados)

            self.buscar_blocos("CPU", LOTE_CPU * trabalhadores, preparar, lote_cpu)

    def buscar_blocos(self, dispositivo, lote, preparar, procurar):
        from test_framework.blocktools import add_witness_commitment, create_block, create_coinbase
        from test_framework.messages import uint256_from_compact

        endereco = self.no.receber()
        premio = bytes.fromhex(self.no.rpc("validateaddress", endereco)["scriptPubKey"])
        aceitos = hashes = 0
        duracao = 0.0
        proxima_taxa = perf_counter()
        self.eventos.put(("minerando", dispositivo))
        while self.continuar.wait() and not self.interromper.is_set():
            self.no.conferir_mineracao()
            modelo = self.no.rpc("getblocktemplate", {"rules": ["segwit"]})
            alvo = uint256_from_compact(int(modelo["bits"], 16))
            coinbase = create_coinbase(modelo["height"], script_pubkey=premio, nValue=0)
            coinbase.vout[0].nValue = modelo["coinbasevalue"]
            bloco = create_block(
                tmpl=modelo, coinbase=coinbase, txlist=[entrada["data"] for entrada in modelo["transactions"]]
            )
            add_witness_commitment(bloco)
            if coinbase.vout[-1].scriptPubKey.hex() != modelo["default_witness_commitment"]:
                raise RuntimeError("O compromisso da testemunha divergiu do modelo do nó.")
            preparar(bloco.serialize()[:80])
            primeiro = 0
            proxima_consulta = perf_counter() + 8
            while self.continuar.wait() and not self.interromper.is_set():
                agora = perf_counter()
                if agora >= proxima_consulta:
                    if self.no.rpc("getbestblockhash") != modelo["previousblockhash"]:
                        break
                    proxima_consulta = agora + 8
                inicio_busca = perf_counter()
                nonce, calculados = procurar(alvo, primeiro)
                fim_busca = perf_counter()
                duracao += fim_busca - inicio_busca
                hashes += calculados
                if fim_busca >= proxima_taxa and duracao > 0:
                    self.eventos.put(("taxa", hashes / duracao / 1e6))
                    hashes = 0
                    duracao = 0.0
                    proxima_taxa = fim_busca + 1
                if nonce is not None:
                    self.continuar.wait()
                    if self.interromper.is_set():
                        return
                    bloco.nNonce = nonce
                    if bloco.hash_int <= alvo and bloco.is_valid():
                        if self.no.rpc("getbestblockhash") != modelo["previousblockhash"]:
                            break
                        self.no.conferir_mineracao()
                        resposta = self.no.rpc("submitblock", bloco.serialize().hex())
                        if resposta is not None:
                            raise RuntimeError(f"O nó recusou o bloco: {resposta}.")
                        cabecalho = self.no.rpc("getblockheader", bloco.hash_hex)
                        if cabecalho["confirmations"] != 1:
                            raise RuntimeError("O bloco encontrado ficou fora da ponta da cadeia.")
                        aceitos += 1
                        self.eventos.put(("bloco", (aceitos, cabecalho["height"])))
                        break
                primeiro += lote
                if primeiro >= LIMITE_NONCE:
                    bloco.nTime = max(int(time()), bloco.nTime + 1)
                    if bloco.nTime >= modelo["curtime"] + 120:
                        break
                    preparar(bloco.serialize()[:80])
                    primeiro = 0
