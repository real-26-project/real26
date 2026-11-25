# Distribuído sob a licença MIT. Consulte COPYING.
"""Prepara o usuário restrito e copia a carteira anterior após desligamento."""

from argparse import ArgumentParser
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tempfile


USUARIO = "real26-wallet"
BASE = Path("/var/lib/real26-wallet")
DADOS = BASE / "no"
ANTIGO = Path("/var/lib/real26-desktop")


def preparar_usuario():
    if os.geteuid() != 0:
        raise PermissionError("A preparação inicial exige o administrador do WSL.")
    try:
        conta = pwd.getpwnam(USUARIO)
    except KeyError:
        subprocess.run(
            [
                "useradd",
                "--system",
                "--user-group",
                "--home-dir",
                str(BASE),
                "--shell",
                "/usr/sbin/nologin",
                USUARIO,
            ],
            check=True,
        )
        conta = pwd.getpwnam(USUARIO)
    if BASE.is_symlink():
        raise RuntimeError("A pasta de dados precisa ser um diretório local.")
    BASE.mkdir(mode=0o700, exist_ok=True)
    # O administrador controla os nomes de perfis; o serviço grava apenas no seu perfil.
    os.chown(BASE, 0, conta.pw_gid)
    BASE.chmod(0o750)
    return conta


@contextmanager
def reservar(origem):
    cadeia = origem / "real26ensaio"
    if origem.is_symlink() or cadeia.is_symlink() or not cadeia.is_dir():
        raise RuntimeError("A origem não contém a cadeia esperada da carteira desktop.")
    fd = os.open(cadeia / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "r+b") as arquivo:
        try:
            fcntl.lockf(arquivo, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as erro:
            raise RuntimeError(
                "O nó anterior está ativo. Encerre a mineração e feche a carteira antes da migração."
            ) from erro
        yield


def migrar(origem, destino, conta):
    if destino.exists() or destino.is_symlink():
        raise RuntimeError("Já existe um perfil no destino. A migração não o substitui.")
    with reservar(origem):
        temporario = Path(tempfile.mkdtemp(prefix=".migracao-", dir=destino.parent))
        try:
            copia = temporario / "no"
            shutil.copytree(
                origem,
                copia,
                symlinks=True,
                ignore=shutil.ignore_patterns(".lock", ".cookie", "bitcoind.pid", "bitcoin.conf"),
            )
            for caminho in [copia, *copia.rglob("*")]:
                if caminho.is_symlink():
                    raise RuntimeError("A migração exige que os dados da carteira sejam arquivos locais.")
                os.chown(caminho, conta.pw_uid, conta.pw_gid)
                caminho.chmod(0o700 if caminho.is_dir() else 0o600)
            copia.rename(destino)
        finally:
            shutil.rmtree(temporario)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--migrar", action="store_true", help="Copia o perfil legado desligado para o usuário restrito."
    )
    args = parser.parse_args()
    conta = preparar_usuario()
    if args.migrar:
        migrar(ANTIGO, DADOS, conta)
        print("Carteira e cadeia copiadas. A pasta anterior foi preservada.")
    elif ANTIGO.exists() and not DADOS.exists():
        print("Perfil anterior encontrado. Use --migrar após desligar o nó anterior.")
    else:
        if DADOS.is_symlink():
            raise RuntimeError("O perfil de dados precisa ser um diretório local.")
        DADOS.mkdir(mode=0o700, exist_ok=True)
        os.chown(DADOS, conta.pw_uid, conta.pw_gid)
        DADOS.chmod(0o700)
        print("Usuário de serviço preparado.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as erro:
        raise SystemExit(str(erro))
