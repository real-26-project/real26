# Distribuído sob a licença MIT. Consulte COPYING.
"""Empacota a carteira Windows e um runtime Python privado usando NSIS."""

from argparse import ArgumentParser
import hashlib
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory


RAIZ = Path(__file__).resolve().parents[1]
FONTE = RAIZ / "carteira-desktop"


def copiar_pacote(destino, binarios):
    python = Path(sys.base_prefix)
    runtime = destino / "runtime"
    runtime.mkdir()
    for arquivo in [*python.glob("*.dll"), python / "python.exe", python / "pythonw.exe", python / "LICENSE.txt"]:
        shutil.copy2(arquivo, runtime)
    ignora = shutil.ignore_patterns(
        "__pycache__", "*.pyc", "site-packages", "test", "tests", "idlelib", "ensurepip"
    )
    for nome in ("Lib", "DLLs", "tcl"):
        shutil.copytree(python / nome, runtime / nome, ignore=ignora)

    fontes = {
        "carteira-desktop": (
            "carteira.py",
            "idiomas.py",
            "no_real26.py",
            "mineracao.py",
            "real26-carteira.png",
            "pares-testnet.txt",
            "real26.ico",
        ),
        "experimentos": ("benchmark_pow_gpu.py", "benchmark-pow.cl", "mineracao_gpu.py"),
    }
    for pasta, arquivos in fontes.items():
        (destino / pasta).mkdir()
        for arquivo in arquivos:
            shutil.copy2(RAIZ / pasta / arquivo, destino / pasta)

    framework = Path("test/functional/test_framework")
    # A mineração reutiliza a montagem de blocos. A suíte funcional fica no repositório.
    modulos_mineracao = (
        "__init__.py",
        "address.py",
        "blocktools.py",
        "descriptors.py",
        "key.py",
        "messages.py",
        "script.py",
        "script_util.py",
        "segwit_addr.py",
        "util.py",
        "crypto/ripemd160.py",
        "crypto/secp256k1.py",
        "crypto/siphash.py",
    )
    for modulo in modulos_mineracao:
        relativo = framework / modulo
        (destino / relativo).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RAIZ / relativo, destino / relativo)
    (destino / "no-windows").mkdir()
    for nome in ("bitcoind.exe", "bitcoin-cli.exe"):
        arquivo = binarios / nome
        with arquivo.open("rb") as entrada:
            cabecalho = entrada.read(64)
            if len(cabecalho) != 64 or cabecalho[:2] != b"MZ":
                raise ValueError(f"O nó precisa ser compilado para Windows x64: {arquivo}")
            entrada.seek(struct.unpack_from("<I", cabecalho, 60)[0])
            if entrada.read(6) != b"PE\0\0\x64\x86":
                raise ValueError(f"O executável precisa ter arquitetura Windows x64: {arquivo}")
        shutil.copy2(arquivo, destino / "no-windows" / nome)
    for arquivo in ("COPYING", "README.pt-BR.md", "SECURITY.md"):
        shutil.copy2(RAIZ / arquivo, destino)


def manifesto(destino, arquivo):
    linhas = []
    for caminho in sorted(destino.rglob("*"), key=lambda item: (len(item.parts), item), reverse=True):
        relativo = caminho.relative_to(destino)
        nome = str(relativo).replace("$", "$$")
        comando = "RMDir" if caminho.is_dir() else "Delete"
        linhas.append(f'    {comando} "$INSTDIR\\{nome}"')
    arquivo.write_text("\n".join(linhas) + "\n", encoding="utf-8-sig")


def compilar(args, origem, remover, saida):
    if args.nsis_wsl:
        wsl = ["wsl.exe", "-d", args.distribuicao, "--exec"]
        base = args.nsis_wsl.rstrip("/")
        comando = [*wsl, "env", f"NSISDIR={base}/share/nsis", f"{base}/bin/makensis"]

        def caminho(arquivo):
            return subprocess.check_output(
                [*wsl, "wslpath", "-a", "-u", arquivo.as_posix()], encoding="utf-8"
            ).strip()

        opcao = "-"
    else:
        comando = [args.makensis]
        caminho = str
        opcao = "/"
    entradas = {"PACOTE": origem, "MANIFESTO": remover, "SAIDA": saida}
    subprocess.run(
        [
            *comando,
            f"{opcao}V2",
            *(f"{opcao}D{nome}={caminho(valor)}" for nome, valor in entradas.items()),
            caminho(FONTE / "instalador.nsi"),
        ],
        check=True,
    )


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--makensis", default="makensis.exe", help="Executável NSIS no Windows.")
    parser.add_argument("--nsis-wsl", help="Prefixo Linux do NSIS, com bin/makensis e share/nsis.")
    parser.add_argument("--distribuicao", default="REAL26-Dev", help="Distribuição WSL usada para compilar.")
    parser.add_argument(
        "--binarios", required=True, type=Path, help="Diretório com o nó REAL-26 compilado para Windows x64."
    )
    args = parser.parse_args()
    if (
        sys.platform != "win32"
        or struct.calcsize("P") != 8
        or platform.machine().lower() not in ("amd64", "x86_64")
    ):
        parser.error("Use um Python Windows de 64 bits com Tcl/Tk instalado.")
    import tkinter

    tkinter.Tcl()

    saida = RAIZ / "releases" / "REAL-26-Carteira-Ensaio-Windows-Nativa-x64.exe"
    saida.parent.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="real26-empacotar-", dir=saida.parent) as temporario:
        trabalho = Path(temporario)
        pacote = trabalho / "pacote"
        pacote.mkdir()
        copiar_pacote(pacote, args.binarios)
        remover = trabalho / "remover.nsh"
        manifesto(pacote, remover)
        gerado = trabalho / saida.name
        compilar(args, pacote, remover, gerado)
        with gerado.open("rb") as arquivo:
            hash_saida = hashlib.file_digest(arquivo, "sha256").hexdigest()
        gerado.replace(saida)
    saida.with_suffix(".exe.sha256").write_text(f"{hash_saida}  {saida.name}\n", encoding="ascii")
    print(saida)
    print(f"SHA-256 {hash_saida}")


if __name__ == "__main__":
    main()
