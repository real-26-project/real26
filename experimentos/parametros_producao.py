# Distribuído sob a licença MIT. Consulte COPYING.
"""Calcula a emissão e a resposta idealizada do ajuste de dificuldade."""
from argparse import ArgumentParser
from decimal import Decimal
from fractions import Fraction
from random import Random
from statistics import median, quantiles


UNIDADE = 100_000_000
RECOMPENSA = 25 * UNIDADE
HALVING = 420_000
INTERVALO = 300
HORA = 3600
DIA = 24 * HORA


def emissao():
    recompensas = [(RECOMPENSA >> era) for era in range(RECOMPENSA.bit_length())]
    # O primeiro período começa na altura zero e o gênese tem recompensa zero.
    unidades = sum(recompensas) * HALVING - RECOMPENSA
    assert unidades < 21_000_000 * UNIDADE
    assert (RECOMPENSA >> len(recompensas)) == 0
    print(f"Emissão máxima teórica: {Decimal(unidades) / UNIDADE:.8f}")
    print(f"Primeira redução: altura {HALVING}; primeiro bloco sem subsídio: {HALVING * len(recompensas)}")
    print(f"Calendário nominal entre reduções: {HALVING * INTERVALO / (365 * 86400):.3f} anos")
    print(f"Emissão diária inicial a {INTERVALO // 60} min/bloco: {RECOMPENSA * (86400 // INTERVALO) // UNIDADE}")
    for eras in (1, 4, 7, len(recompensas)):
        parcial = sum(recompensas[:eras]) * HALVING - RECOMPENSA
        anos = eras * HALVING * INTERVALO / (365 * 86400)
        periodo = "período" if eras == 1 else "períodos"
        print(f"Após {eras} {periodo} ({anos:.2f} anos): {Decimal(parcial) / UNIDADE:.8f} "
              f"({100 * parcial / unidades:.2f}% do máximo)")


def ajustar(janela, mudanca):
    # O modelo assume poder de mineração constante depois de uma mudança
    # na fronteira do período e horários igualmente espaçados.
    segundos = Fraction(INTERVALO, mudanca)
    periodo = INTERVALO * janela
    resultado = []
    for _ in range(3):
        resultado.append((float(segundos), float(segundos * janela / 3600)))
        observado = segundos * (janela - 1)
        multiplicador = max(Fraction(1, 4), min(observado / periodo, Fraction(4)))
        segundos /= multiplicador
    return resultado


def alvo_compacto(alvo):
    if not 0 < alvo < 1 << 256:
        raise ValueError("Alvo fora do intervalo de 256 bits.")
    tamanho = (alvo.bit_length() + 7) // 8
    deslocamento = 8 * (tamanho - 3)
    mantissa = alvo >> deslocamento if deslocamento >= 0 else alvo << -deslocamento
    if mantissa & 0x800000:
        tamanho += 1
        mantissa >>= 8
    return tamanho << 24 | mantissa


def expandir_alvo(bits):
    tamanho = bits >> 24
    mantissa = bits & 0x7fffff
    deslocamento = 8 * (tamanho - 3)
    return mantissa << deslocamento if deslocamento >= 0 else mantissa >> -deslocamento


def partida(taxa):
    # Um hash encontra o bloco se cair entre zero e o alvo, inclusive.
    alvo = (1 << 256) // (taxa * INTERVALO) - 1
    bits = alvo_compacto(alvo)
    real = expandir_alvo(bits)
    assert 0 < real <= alvo
    segundos = Fraction(1 << 256, (real + 1) * taxa)
    return bits, float(segundos)


def mostrar_partida(rotulo, taxa):
    bits, segundos = partida(taxa)
    print(f"{rotulo}: {taxa:,} H/s; nBits = 0x{bits:08x}; média de {segundos:.4f} s")


def simular(rng, potencia, janela, meia_vida, desvio=0):
    """Modelo estocástico de uma mudança permanente na fronteira da janela.

    O alvo é relativo ao alvo inicial. Cada espera é exponencial e o relógio
    informado pelos blocos pode divergir do tempo real por um desvio constante.
    """
    tempo = 0.0
    alvo = 1.0
    altura = diaria = semanal = consecutivos = 0
    primeiro_horario = 0.0
    estabilizou = None
    while tempo < 7 * DIA:
        media = INTERVALO / (potencia * alvo)
        if 0.9 * INTERVALO <= media <= 1.1 * INTERVALO:
            if consecutivos == 0:
                inicio_faixa = tempo
            consecutivos += 1
            if consecutivos == 24 and estabilizou is None:
                estabilizou = inicio_faixa
        else:
            consecutivos = 0

        tempo += rng.expovariate(1 / media)
        altura += 1
        diaria += tempo <= DIA
        semanal += tempo <= 7 * DIA
        horario = tempo + desvio
        if meia_vida:
            alvo = 2 ** ((horario - INTERVALO * altura) / meia_vida)
        elif altura % janela == janela - 1:
            observado = horario - primeiro_horario
            alvo *= max(0.25, min(4.0, observado / (janela * INTERVALO)))
        elif altura % janela == 0:
            primeiro_horario = horario

    nominal_diario = DIA // INTERVALO
    subsidio = RECOMPENSA // UNIDADE
    return ((diaria - nominal_diario) * subsidio, (semanal - 7 * nominal_diario) * subsidio, estabilizou)


def comparar_dificuldade(rodadas):
    regras = (("144 blocos", 144, 0), ("2.016 blocos", 2016, 0),
              ("ASERT 3 h", 0, 3 * HORA), ("ASERT 6 h", 0, 6 * HORA),
              ("ASERT 12 h", 0, 12 * HORA), ("ASERT 48 h", 0, 48 * HORA))
    cenarios = (("potência estável", 1, 0), ("potência dobra", 2, 0),
                ("potência multiplicada por dez", 10, 0), ("metade da potência", 0.5, 0),
                ("10% da potência", 0.1, 0), ("horários +1 h", 1, HORA))
    print(f"{rodadas} simulações por cenário e regra, sementes de 0 a {rodadas - 1}.")
    print("Emissão é o desvio do calendário nominal em REAL-26. Recuperação exige 24 blocos "
          "consecutivos com média esperada de 4,5 a 5,5 minutos.")
    for cenario, potencia, desvio in cenarios:
        print(f"\n{cenario}")
        for nome, janela, meia_vida in regras:
            dia, semana, tempos = zip(*(simular(Random(i), potencia, janela, meia_vida, desvio)
                                        for i in range(rodadas)))
            recuperadas = [t for t in tempos if t is not None]
            p90_dia = quantiles(dia, n=10, method="inclusive")[8]
            prazo = f"{median(recuperadas) / HORA:.1f} h" if recuperadas else "—"
            print(f"{nome:14}  24 h {median(dia):+8.0f} (p90 {p90_dia:+8.0f})"
                  f"  7 d {median(semana):+8.0f}  recuperação {prazo:>7} [{len(recuperadas)}/{rodadas}]")


def main():
    parser = ArgumentParser(description=__doc__)
    modos = parser.add_mutually_exclusive_group()
    modos.add_argument("--hashrate", type=int, help="Taxa agregada dos mineradores em hashes por segundo.")
    modos.add_argument("--comparar-dificuldade", type=int, metavar="RODADAS", help="Compara as regras por simulação.")
    args = parser.parse_args()
    if args.comparar_dificuldade is not None:
        if args.comparar_dificuldade < 2:
            parser.error("A comparação exige pelo menos duas simulações por cenário.")
        comparar_dificuldade(args.comparar_dificuldade)
        return
    if args.hashrate is not None:
        if args.hashrate <= 0:
            parser.error("A taxa deve ser positiva.")
        try:
            mostrar_partida("Taxa informada", args.hashrate)
        except ValueError as erro:
            parser.error(str(erro))
        return

    assert alvo_compacto(expandir_alvo(0x1d00ffff)) == 0x1d00ffff
    emissao()
    for janela in (144, 2016):
        for mudanca in (Fraction(1, 10), Fraction(1, 2), Fraction(2), Fraction(10)):
            periodos = ajustar(janela, mudanca)
            print(f"{janela} blocos, mineração x{float(mudanca):g}: "
                  + ", ".join(f"{segundos:.2f} s/bloco por {horas:.2f} h" for segundos, horas in periodos))
    for rotulo, taxa in (
        ("CPU do ensaio", 14_537_500),
        ("Radeon do ensaio", 256_060_000),
        ("Um ASIC de 104 TH/s", 104 * 10**12),
        ("Um ASIC de 200 TH/s", 200 * 10**12),
        ("Dois ASICs de 104 TH/s", 208 * 10**12),
        ("Três ASICs de 104 TH/s", 312 * 10**12),
    ):
        mostrar_partida(rotulo, taxa)

    for disponivel in (Fraction(1, 2), Fraction(2, 3), Fraction(1, 3)):
        primeiro, depois, _ = ajustar(144, disponivel)
        print(f"Taxa restante {float(disponivel):.1%}: "
              f"{primeiro[0] / 60:.2f} min/bloco por {primeiro[1]:.2f} h; "
              f"após ajuste: {depois[0] / 60:.2f} min/bloco.")


if __name__ == "__main__":
    main()
