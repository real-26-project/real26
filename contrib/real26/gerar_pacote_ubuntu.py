#!/usr/bin/env python3
# Distribuído sob a licença MIT. Consulte COPYING.
"""Empacota os binários Linux da REAL-26 para a testnet no Ubuntu x86_64."""

from argparse import ArgumentParser
from gzip import GzipFile
from hashlib import file_digest
from io import BytesIO
from pathlib import Path
from tarfile import TarInfo, TarFile
from tempfile import TemporaryDirectory


RAIZ = Path(__file__).resolve().parents[2]
SERVICO = Path(__file__).with_name("real26-testnet.service")
LICENCAS = {
    "COPYING": RAIZ / "COPYING",
    "licencas/README.md": RAIZ / "licencas/README.md",
    "licencas/liboqs-0.16.0.txt": RAIZ / "licencas/liboqs-0.16.0.txt",
    "licencas/mldsa-native.txt": RAIZ / "licencas/mldsa-native.txt",
    "licencas/leveldb.txt": RAIZ / "src/leveldb/LICENSE",
    "licencas/crc32c.txt": RAIZ / "src/crc32c/LICENSE",
    "licencas/minisketch.txt": RAIZ / "src/minisketch/LICENSE",
    "licencas/secp256k1.txt": RAIZ / "src/secp256k1/COPYING",
}


def empacotar(binarios, destino):
    executaveis = {"real26d": binarios / "bitcoind", "real26-cli": binarios / "bitcoin-cli"}
    arquivos = {nome: (caminho, 0o755) for nome, caminho in executaveis.items()}
    for caminho, _ in arquivos.values():
        with caminho.open("rb") as arquivo:
            cabecalho = arquivo.read(20)
        if not cabecalho.startswith(b"\x7fELF\x02\x01") or cabecalho[18:20] != b"\x3e\x00":
            raise ValueError(f"Binário inválido para Linux x86_64: {caminho}")
    arquivos[SERVICO.name] = (SERVICO, 0o644)
    arquivos.update({nome: (caminho, 0o644) for nome, caminho in LICENCAS.items()})

    destino.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".real26-", dir=destino.parent) as pasta:
        temporario = Path(pasta) / destino.name
        with temporario.open("wb") as saida:
            with GzipFile(filename="", mode="wb", fileobj=saida, mtime=0) as gzip:
                with TarFile(fileobj=gzip, mode="w") as pacote:
                    for nome, (caminho, modo) in arquivos.items():
                        info = TarInfo(nome)
                        info.mode = modo
                        if nome in executaveis:
                            with caminho.open("rb") as entrada:
                                info.size = caminho.stat().st_size
                                pacote.addfile(info, entrada)
                        else:
                            conteudo = caminho.read_bytes().replace(b"\r\n", b"\n")
                            info.size = len(conteudo)
                            pacote.addfile(info, BytesIO(conteudo))
        with temporario.open("rb") as arquivo:
            sha = file_digest(arquivo, "sha256").hexdigest()
        manifesto = temporario.with_name(destino.name + ".sha256")
        manifesto.write_text(f"{sha}  {destino.name}\n", encoding="ascii", newline="\n")
        temporario.replace(destino)
        manifesto.replace(destino.with_name(manifesto.name))
    print(f"{sha}  {destino}")


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--binarios", type=Path, required=True)
    parser.add_argument("--saida", type=Path, required=True)
    args = parser.parse_args()
    empacotar(args.binarios, args.saida)
