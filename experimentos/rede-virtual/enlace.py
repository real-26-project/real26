# Distribuído sob a licença MIT. Consulte COPYING.
"""Emula atraso e banda em cada sentido entre duas interfaces QEMU."""

import asyncio
import struct
import sys

ATRASO = 0.025
BYTES_POR_SEGUNDO = 20_000_000 / 8


async def direcao(origem, destino):
    fila = asyncio.Queue(maxsize=4096)
    relogio = asyncio.get_running_loop()

    async def receber():
        livre_em = 0
        while True:
            prefixo = await origem.readexactly(4)
            tamanho, = struct.unpack("!I", prefixo)
            if not 1 <= tamanho <= 65536:
                raise ValueError("Quadro inválido no enlace QEMU.")
            quadro = await origem.readexactly(tamanho)
            livre_em = max(livre_em, relogio.time()) + tamanho / BYTES_POR_SEGUNDO
            await fila.put((livre_em + ATRASO, prefixo + quadro))

    async def enviar():
        while True:
            entrega, quadro = await fila.get()
            atraso = entrega - relogio.time()
            if atraso > 0:
                await asyncio.sleep(atraso)
            destino.write(quadro)
            await destino.drain()

    tarefas = [asyncio.create_task(receber()), asyncio.create_task(enviar())]
    try:
        await asyncio.gather(*tarefas)
    finally:
        for tarefa in tarefas:
            tarefa.cancel()
        await asyncio.gather(*tarefas, return_exceptions=True)


async def conectar(leitor, escritor, porta_origem):
    outro_escritor = None
    tarefas = []
    try:
        outro_leitor, outro_escritor = await asyncio.open_connection("127.0.0.1", porta_origem)
        tarefas = [asyncio.create_task(direcao(leitor, outro_escritor)),
                   asyncio.create_task(direcao(outro_leitor, escritor))]
        await asyncio.gather(*tarefas)
    except (asyncio.IncompleteReadError, ConnectionError):
        pass
    finally:
        for tarefa in tarefas:
            tarefa.cancel()
        await asyncio.gather(*tarefas, return_exceptions=True)
        escritor.close()
        if outro_escritor is not None:
            outro_escritor.close()


async def main():
    porta_origem, porta_entrada = map(int, sys.argv[1:])
    servidor = await asyncio.start_server(
        lambda leitor, escritor: conectar(leitor, escritor, porta_origem),
        "127.0.0.1", porta_entrada,
    )
    async with servidor:
        print("Enlace pronto: 25 ms e 20 Mbit/s por direção.", flush=True)
        await servidor.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
