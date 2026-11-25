# Distribuído sob a licença MIT. Consulte COPYING.
"""Mede SHA-256 duplo em uma GPU OpenCL no Windows."""
from argparse import ArgumentParser
import ctypes as c
from hashlib import sha256
from pathlib import Path
from statistics import median
import struct
import subprocess
from time import perf_counter


LOTE = 1 << 18
CABECALHO = (
    struct.pack("<I", 1) + bytes(32)
    + bytes.fromhex("b53ad1e70716babad02af3396c52a3125d494ff675c512ee6aa4bce46dccceab")[::-1]
    + struct.pack("<III", 1795132800, 0x1d00ffff, 0)
)
P = c.c_void_p
U = c.c_uint
I = c.c_int
T = c.c_size_t
L = c.c_uint64


def conferir(codigo, operacao):
    if codigo != 0:
        raise RuntimeError(f"{operacao} falhou com código OpenCL {codigo}.")


class GPU:
    def __init__(self):
        self.api = c.WinDLL("OpenCL.dll")
        self.recursos = []
        for nome, retorno, argumentos in (
            ("clGetPlatformIDs", I, [U, c.POINTER(P), c.POINTER(U)]),
            ("clGetDeviceIDs", I, [P, L, U, c.POINTER(P), c.POINTER(U)]),
            ("clGetDeviceInfo", I, [P, U, T, P, c.POINTER(T)]),
            ("clCreateContext", P, [P, U, c.POINTER(P), P, P, c.POINTER(I)]),
            ("clCreateCommandQueue", P, [P, P, L, c.POINTER(I)]),
            ("clCreateProgramWithSource", P, [P, U, c.POINTER(c.c_char_p), c.POINTER(T), c.POINTER(I)]),
            ("clBuildProgram", I, [P, U, c.POINTER(P), c.c_char_p, P, P]),
            ("clGetProgramBuildInfo", I, [P, P, U, T, P, c.POINTER(T)]),
            ("clCreateKernel", P, [P, c.c_char_p, c.POINTER(I)]),
            ("clCreateBuffer", P, [P, L, T, P, c.POINTER(I)]),
            ("clSetKernelArg", I, [P, U, T, P]),
            ("clEnqueueNDRangeKernel", I, [P, P, U, P, c.POINTER(T), P, U, P, P]),
            ("clEnqueueReadBuffer", I, [P, P, U, T, T, P, U, P, P]),
            ("clEnqueueWriteBuffer", I, [P, P, U, T, T, P, U, P, P]),
            ("clFinish", I, [P]),
        ):
            funcao = getattr(self.api, nome)
            funcao.restype = retorno
            funcao.argtypes = argumentos
        self.nonce = 0

    def criar(self, tipo, funcao, *args):
        erro = I()
        objeto = P(funcao(*args, c.byref(erro)))
        conferir(erro.value, funcao.__name__)
        self.recursos.append((tipo, objeto))
        return objeto

    def __enter__(self):
        try:
            self.preparar()
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *_):
        for tipo, objeto in reversed(self.recursos):
            liberar = getattr(self.api, "clRelease" + tipo)
            liberar.argtypes = [P]
            liberar.restype = I
            liberar(objeto)
        self.recursos.clear()

    def preparar(self):
        api = self.api
        quantidade = U()
        conferir(api.clGetPlatformIDs(0, None, c.byref(quantidade)), "Listar plataformas")
        plataformas = (P * quantidade.value)()
        conferir(api.clGetPlatformIDs(quantidade, plataformas, None), "Ler plataformas")
        dispositivo = P()
        for plataforma in plataformas:
            if api.clGetDeviceIDs(plataforma, 4, 1, c.byref(dispositivo), None) == 0:
                break
        if not dispositivo:
            raise RuntimeError("Nenhuma GPU OpenCL disponível.")
        nome = c.create_string_buffer(256)
        conferir(api.clGetDeviceInfo(dispositivo, 0x102b, len(nome), nome, None), "Ler nome da GPU")
        print("GPU:", nome.value.decode(), flush=True)
        contexto = self.criar("Context", api.clCreateContext, None, 1, c.byref(dispositivo), None, None)
        self.fila = self.criar("CommandQueue", api.clCreateCommandQueue, contexto, dispositivo, 0)
        fonte = c.c_char_p(Path(__file__).with_name("benchmark-pow.cl").read_bytes())
        programa = self.criar("Program", api.clCreateProgramWithSource, contexto, 1, c.byref(fonte), None)
        retorno = api.clBuildProgram(programa, 1, c.byref(dispositivo), None, None, None)
        if retorno != 0:
            tamanho = T()
            api.clGetProgramBuildInfo(programa, dispositivo, 0x1183, 0, None, c.byref(tamanho))
            log = c.create_string_buffer(tamanho.value)
            api.clGetProgramBuildInfo(programa, dispositivo, 0x1183, tamanho, log, None)
            raise RuntimeError(log.value.decode(errors="replace"))
        self.kernel = self.criar("Kernel", api.clCreateKernel, programa, b"medir")
        self.busca = self.criar("Kernel", api.clCreateKernel, programa, b"procurar")
        palavras = (U * 20)(*struct.unpack(">20I", CABECALHO))
        self.entrada = self.criar("MemObject", api.clCreateBuffer, contexto, 4 | 32, c.sizeof(palavras), palavras)
        self.saida = self.criar("MemObject", api.clCreateBuffer, contexto, 2, 4 * LOTE, None)
        self.candidato = self.criar("MemObject", api.clCreateBuffer, contexto, 1, c.sizeof(U), None)
        for kernel, saida in ((self.kernel, self.saida), (self.busca, self.candidato)):
            for indice, objeto in ((0, self.entrada), (2, saida)):
                conferir(api.clSetKernelArg(kernel, indice, c.sizeof(objeto), c.byref(objeto)), "Configurar buffer")

    def preparar_busca(self, cabecalho):
        palavras = (U * 20)(*struct.unpack(">20I", cabecalho))
        conferir(self.api.clEnqueueWriteBuffer(
            self.fila, self.entrada, 1, 0, c.sizeof(palavras), palavras, 0, None, None
        ), "Carregar cabeçalho")

    def procurar(self, nonce, prefixo_alvo=0):
        api = self.api
        inicio = U(nonce)
        tamanho = T(LOTE)
        candidato = U(0xffffffff)
        conferir(api.clEnqueueWriteBuffer(
            self.fila, self.candidato, 1, 0, c.sizeof(candidato), c.byref(candidato), 0, None, None
        ), "Limpar resultado")
        conferir(api.clSetKernelArg(self.busca, 1, c.sizeof(inicio), c.byref(inicio)), "Configurar nonce")
        limite = U(prefixo_alvo)
        conferir(api.clSetKernelArg(self.busca, 3, c.sizeof(limite), c.byref(limite)), "Configurar alvo")
        conferir(api.clEnqueueNDRangeKernel(self.fila, self.busca, 1, None, c.byref(tamanho), None, 0, None, None), "Buscar nonce")
        conferir(api.clEnqueueReadBuffer(
            self.fila, self.candidato, 1, 0, c.sizeof(candidato), c.byref(candidato), 0, None, None
        ), "Ler nonce encontrado")
        return nonce + candidato.value if candidato.value < LOTE else None

    def executar(self):
        api = self.api
        inicio = U(self.nonce)
        tamanho = T(LOTE)
        conferir(api.clSetKernelArg(self.kernel, 1, c.sizeof(inicio), c.byref(inicio)), "Configurar nonce")
        conferir(api.clEnqueueNDRangeKernel(self.fila, self.kernel, 1, None, c.byref(tamanho), None, 0, None, None), "Executar GPU")
        conferir(api.clFinish(self.fila), "Aguardar GPU")
        self.nonce = (self.nonce + LOTE) % (1 << 32)

    def validar(self):
        inicio = self.nonce
        self.executar()
        for indice in (0, 1, LOTE // 2, LOTE - 1):
            palavra = U()
            conferir(self.api.clEnqueueReadBuffer(self.fila, self.saida, 1, 4 * indice, 4, c.byref(palavra), 0, None, None), "Ler hash")
            cabecalho = CABECALHO[:76] + struct.pack("<I", inicio + indice)
            esperado = sha256(sha256(cabecalho).digest()).digest()
            assert palavra.value == int.from_bytes(esperado[:4], "big")
        print("Prefixos de quatro hashes da GPU conferidos com a CPU.", flush=True)

    def medir(self, segundos=4):
        inicio = perf_counter()
        lotes = 0
        while perf_counter() - inicio < segundos:
            self.executar()
            lotes += 1
        return lotes * LOTE / (perf_counter() - inicio) / 1_000_000


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--cpu-wsl", help="Executável Linux do benchmark de CPU na distribuição REAL26-Dev.")
    parser.add_argument("--threads", type=int, default=28)
    args = parser.parse_args()
    with GPU() as gpu:
        gpu.validar()
        taxas = [gpu.medir() for _ in range(3)]
        print(f"GPU sozinha: {taxas} MH/s; mediana {median(taxas):.3f} MH/s.", flush=True)
        if args.cpu_wsl:
            cmd = ["wsl", "-d", "REAL26-Dev", "-u", "root", "--", args.cpu_wsl, CABECALHO.hex(), str(args.threads)]
            with subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE) as cpu:
                print(cpu.stdout.readline().rstrip(), flush=True)
                inicio = perf_counter()
                lotes = 0
                while cpu.poll() is None:
                    gpu.executar()
                    lotes += 1
                taxa_gpu = lotes * LOTE / (perf_counter() - inicio) / 1_000_000
                print(cpu.stdout.read().strip(), flush=True)
                if cpu.returncode:
                    raise RuntimeError(f"O benchmark da CPU terminou com código {cpu.returncode}.")
                print(f"GPU com CPU ativa: {taxa_gpu:.3f} MH/s.", flush=True)


if __name__ == "__main__":
    main()
