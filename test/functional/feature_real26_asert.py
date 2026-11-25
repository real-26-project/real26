#!/usr/bin/env python3
# Distribuído sob a licença MIT. Consulte COPYING.
"""Valida o laboratório ASERT com dois nós e horários controlados."""

from test_framework.blocktools import create_block
from test_framework.messages import uint256_from_compact
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import append_config, assert_equal


GENESE = "0313193a95e2e977a045797c0c73490abe285ef0cf472a912f2ffcc6d21082b5"
BITS_INICIAIS = 0x200FFFFF
BITS_LIMITE = 0x207FFFFF
INTERVALO = 300
MEIA_VIDA = 3 * 3600


def alvo_esperado(altura, segundos, bits_iniciais=BITS_INICIAIS, bits_limite=BITS_LIMITE):
    # aserti3-2d com a âncora no gênese e aritmética inteira sem limite de largura em Python.
    numerador = (segundos - altura * INTERVALO) * 65536
    expoente = abs(numerador) // MEIA_VIDA
    if numerador < 0:
        expoente = -expoente
    inteiro, fracao = divmod(expoente, 65536)
    fator = 65536 + ((195766423245049 * fracao + 971821376 * fracao**2
                     + 5127 * fracao**3 + 2**47) // 2**48)
    produto = uint256_from_compact(bits_iniciais) * fator
    alvo = produto >> (16 - inteiro) if inteiro < 16 else produto << (inteiro - 16)
    alvo = min(max(alvo, 1), uint256_from_compact(bits_limite))
    tamanho = (alvo.bit_length() + 7) // 8
    mantissa = alvo >> (8 * max(tamanho - 3, 0))
    if tamanho < 3:
        mantissa <<= 8 * (3 - tamanho)
    if mantissa & 0x800000:
        mantissa >>= 8
        tamanho += 1
    return (tamanho << 24) | mantissa


class Real26AsertTest(BitcoinTestFramework):
    def set_test_params(self):
        self.num_nodes = 2
        self.setup_clean_chain = True

    def setup_network(self):
        self.add_nodes(self.num_nodes)
        for node in self.nodes:
            append_config(node.datadir_path, ["real26asert=1"])
            node.chain = "real26asert-lab"
        self.start_nodes()
        self.connect_nodes(0, 1)

    def run_test(self):
        minerador, validador = self.nodes
        t0 = minerador.getblockheader(GENESE)["time"]
        for node in self.nodes:
            assert_equal(node.getbestblockhash(), GENESE)
            node.setmocktime(t0 + 17 * 3600)

        def verificar_alvo():
            altura = minerador.getblockcount()
            cabecalho = minerador.getblockheader(minerador.getbestblockhash())
            esperado = alvo_esperado(altura, cabecalho["time"] - t0)
            for node in self.nodes:
                bits = node.getblocktemplate({"rules": ["segwit"]})["bits"]
                assert_equal(int(bits, 16), esperado)
            return esperado

        def candidato(horario, bits):
            bloco = create_block(int(minerador.getbestblockhash(), 16),
                                 height=minerador.getblockcount() + 1, ntime=horario)
            bloco.nBits = bits
            bloco.solve()
            return bloco.serialize().hex()

        def minerar(horario):
            bits = verificar_alvo()
            assert_equal(minerador.submitblock(candidato(horario, bits)), None)
            self.sync_blocks()

        assert_equal(verificar_alvo(), BITS_INICIAIS)
        minerar(t0 + INTERVALO)
        assert_equal(verificar_alvo(), BITS_INICIAIS)
        self.log.info("Simulando chegada acelerada de blocos")
        for passo in range(1, 13):
            minerar(t0 + INTERVALO + 30 * passo)
        assert verificar_alvo() < BITS_INICIAIS

        self.log.info("Rejeitando prova de trabalho com alvo incorreto nos dois nós")
        invalido = candidato(t0 + 1000, BITS_INICIAIS)
        for node in self.nodes:
            assert_equal(node.submitblock(invalido), "bad-diffbits")

        self.log.info("Simulando queda de potência e verificando o limite de alvo")
        minerar(t0 + 14 * INTERVALO + MEIA_VIDA)
        assert_equal(verificar_alvo(), 0x201FFFFE)
        minerar(t0 + 15 * INTERVALO + 5 * MEIA_VIDA)
        assert_equal(verificar_alvo(), BITS_LIMITE)

        topo = minerador.getbestblockhash()
        cabecalho = minerador.getblockheader(topo)
        bits = verificar_alvo()
        self.log.info("Rejeitando horários fora dos limites de consenso")
        for node in self.nodes:
            node.setmocktime(cabecalho["time"])
        recente_demais = candidato(cabecalho["time"] + 7201, bits)
        antigo_demais = candidato(cabecalho["mediantime"], bits)
        for node in self.nodes:
            assert_equal(node.submitblock(recente_demais), "time-too-new")
            assert_equal(node.submitblock(antigo_demais), "time-too-old")
            assert_equal(node.getbestblockhash(), topo)


if __name__ == "__main__":
    Real26AsertTest(__file__).main()
