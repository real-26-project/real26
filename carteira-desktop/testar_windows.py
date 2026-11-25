# Distribuído sob a licença MIT. Consulte COPYING.
"""Valida o nó e a carteira nativos em um perfil temporário de ensaio."""

from argparse import ArgumentParser
from decimal import Decimal
from pathlib import Path
from secrets import token_urlsafe
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep

from no_real26 import NoReal26, SenhaIncorreta


def impedir_wsl(evento, dados):
    if evento != "subprocess.Popen":
        return
    executavel, linha, *_ = dados
    if executavel is None:
        executavel = linha.split('"', 2)[1] if linha.startswith('"') else linha.split(maxsplit=1)[0]
    if Path(executavel).name.casefold() in ("wsl", "wsl.exe"):
        raise AssertionError("A carteira nativa tentou iniciar o WSL.")


def testar(binarios, pasta, porta):
    no = NoReal26(pasta / "perfil de ensaio ç", porta, binarios=binarios)
    senha = token_urlsafe(24)
    senha_destino = token_urlsafe(24)
    backup = pasta / "backup de recuperação.dat"
    try:
        no.conectar()
        assert no.estado()["altura"] == 0
        origem = no.criar(senha, "origem")
        assert no.estado()["bloqueada"]
        outra_sessao = NoReal26(no.datadir, porta, binarios=binarios)
        outra_sessao.conectar()
        try:
            outra_sessao.abrir("origem", "senha incorreta de teste")
        except SenhaIncorreta:
            assert "origem" in no.rpc("listwallets")
        else:
            raise AssertionError("A segunda sessão aceitou a senha incorreta.")
        outra_sessao.abrir("origem", senha)
        assert outra_sessao.estado()["bloqueada"]
        outra_sessao.sair()
        assert "origem" in no.rpc("listwallets")
        no.backup(str(backup))
        no.sair()
        destino = no.criar(senha_destino, "destino")
        no.sair()
        no.abrir("origem", senha)

        assert len(no.rpc("generatetoaddress", 103, origem, 100_000_000)) == 103
        taxa = no.estimar_taxa(destino, "1")
        try:
            no.enviar(destino, "1", taxa, "senha incorreta de teste")
        except SenhaIncorreta:
            assert not no.rpc("getrawmempool") and no.estado()["bloqueada"]
        else:
            raise AssertionError("A carteira aceitou a senha incorreta.")

        txid, aviso = no.enviar(destino, "1", taxa, senha)
        assert not aviso and no.estado()["bloqueada"]
        assert no.rpc("getmempoolentry", txid)["fees"]["base"] == Decimal(taxa)
        no.rpc("generatetoaddress", 1, origem, 100_000_000)
        no.sair()
        no.abrir("destino", senha_destino)
        tx = no.rpc("gettransaction", txid, carteira=True)
        assert tx["confirmations"] == 1 and tx["amount"] == 1
        no.sair()
        no.restaurar(str(backup), "recuperada")
        no.abrir("recuperada", senha)
        assert no.receber() == origem and no.estado()["bloqueada"]
        topo = no.rpc("getbestblockhash")
        no.encerrar_no_proprio()
        assert no.processo is not None and no.processo.returncode == 0
        no.conectar()
        assert no.rpc("getbestblockhash") == topo
        assert "recuperada" in no.carteiras()
    finally:
        no.encerrar_no_proprio()


def porta_local():
    with socket.socket() as socket_local:
        socket_local.bind(("127.0.0.1", 0))
        return socket_local.getsockname()[1]


def testar_partida_testnet(binarios, pasta):
    portas = set()
    while len(portas) < 3:
        portas.add(porta_local())
    rpc_servidor, rpc_cliente, p2p = portas
    par = f"127.0.0.1:{p2p}"
    servidor = NoReal26(pasta / "servidor", rpc_servidor, binarios=binarios, compartilhado=True)
    servidor.datadir.mkdir()
    cliente = NoReal26(pasta / "cliente", rpc_cliente, binarios=binarios, pares=(par,), compartilhado=True)
    with subprocess.Popen(
        (servidor.no, *servidor.opcoes, f"-bind={par}", "-listen=1", "-connect=0", "-listenonion=0", "-natpmp=0"),
        creationflags=subprocess.CREATE_NO_WINDOW,
    ) as processo:
        try:
            cliente.conectar()
            assert not cliente.rede_pronta_para_minerar(cliente.rpc("getblockchaininfo"), [])
            limite = monotonic() + 15
            dados = cliente.estado()
            while not dados["pode_minerar"] and monotonic() < limite:
                sleep(0.2)
                dados = cliente.estado()
            assert dados["altura"] == 0 and dados["sincronizando"] and dados["pode_minerar"]
            cadeia = cliente.rpc("getblockchaininfo")
            pares = cliente.pares_conectados()
            assert not cliente.rede_pronta_para_minerar({**cadeia, "headers": 1}, pares)
            assert not cliente.rede_pronta_para_minerar(cadeia, [{**pares[0], "presynced_headers": 1}])

            cliente.criar(token_urlsafe(24), "primeiro-bloco")
            modelo = cliente.rpc("getblocktemplate", {"rules": ["segwit"]})
            assert modelo["height"] == 1 and modelo["bits"] == "1c10e331"
            assert modelo["previousblockhash"] == servidor.rpc("getbestblockhash")
        finally:
            cliente.encerrar_no_proprio()
            if processo.poll() is None:
                servidor.rpc("stop")
                processo.wait(timeout=15)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--binarios", required=True, type=Path, help="Pasta dos binários nativos Windows x64.")
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("Execute o teste no Windows.")
    sys.addaudithook(impedir_wsl)
    with TemporaryDirectory(prefix="real26-teste-nativo-") as pasta:
        testar(args.binarios, Path(pasta), porta_local())
        testar_partida_testnet(args.binarios, Path(pasta))
    print("Nó nativo validado: pagamento confirmado, backup restaurado e cadeia preservada após reinício.")
    print("Testnet compartilhada validada a partir do gênese com dois nós e o alvo inicial esperado.")


if __name__ == "__main__":
    main()
