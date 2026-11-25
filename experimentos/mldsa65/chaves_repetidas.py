# Distribuído sob a licença MIT. Consulte COPYING.
"""Mede em laboratório uma codificação de testemunha com referências à chave."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from statistics import median
import subprocess
from time import perf_counter

from test_framework.blocktools import add_witness_commitment, create_block, create_coinbase
from test_framework.messages import COIN, COutPoint, CTransaction, CTxIn, CTxOut, ser_vector, tx_from_hex


def assinar(assinador, chaves, entradas, fonte=1):
    origem = b"\x52\x20" + sha256(chaves[:1952]).digest()
    destino = b"\x52\x20" + sha256(b"destino de laboratorio").digest()
    anterior = CTxOut(COIN, origem)
    tx = CTransaction()
    tx.version = 2
    tx.vin = [CTxIn(COutPoint(fonte, indice)) for indice in range(entradas)]
    tx.vout = [CTxOut(100_000, destino), CTxOut(entradas * COIN - 110_000, origem)]
    dados = chaves + tx.serialize_without_witness() + ser_vector([anterior] * entradas)
    return tx_from_hex(subprocess.check_output([assinador, "assinar-tx"], input=dados).hex())


def comprimir_testemunhas(tx):
    comprimida = deepcopy(tx)
    testemunhas = comprimida.wit.vtxinwit
    primeiras = {}
    for indice, testemunha in enumerate(testemunhas):
        assinatura, publica = testemunha.scriptWitness.stack
        if publica in primeiras:
            # Referência experimental de um byte ao índice da entrada anterior.
            testemunha.scriptWitness.stack = [assinatura, bytes([primeiras[publica]])]
        else:
            primeiras[publica] = indice

    return comprimida


def restaurar_chaves(tx):
    chaves_inteiras = {}
    testemunhas = []
    for indice, testemunha in enumerate(tx.wit.vtxinwit):
        assinatura, chave = testemunha.scriptWitness.stack
        if len(chave) == 1952:
            chaves_inteiras[indice] = chave
        elif len(chave) == 1 and chave[0] in chaves_inteiras:
            chave = chaves_inteiras[chave[0]]
        else:
            raise ValueError("A referência deve apontar para uma chave completa em uma entrada anterior.")
        testemunhas.append([assinatura, chave])
    return testemunhas


def conferir_reconstrucao(original, comprimida):
    assert restaurar_chaves(comprimida) == [w.scriptWitness.stack for w in original.wit.vtxinwit]
    assert comprimida.serialize_without_witness() == original.serialize_without_witness()


def medir_bloco(assinador, chaves):
    originais = [assinar(assinador, chaves, 1 + (i < 139), fonte=i + 1) for i in range(555)]
    comprimidas = [comprimir_testemunhas(tx) for tx in originais]
    for original, comprimida in zip(originais, comprimidas):
        conferir_reconstrucao(original, comprimida)

    # Um bloco para cada representação, com compromisso de testemunha próprio.
    origem = b"\x52\x20" + sha256(chaves[:1952]).digest()
    blocos = [
        create_block(hashprev=1, coinbase=create_coinbase(200, script_pubkey=origem), txlist=transacoes)
        for transacoes in (originais, comprimidas)
    ]
    for bloco in blocos:
        add_witness_commitment(bloco)
        assert bloco.get_weight() <= 4_000_000

    antes, depois = (len(bloco.serialize()) for bloco in blocos)
    economia = antes - depois
    assert economia == 139 * 1953
    amostras = []
    for _ in range(31):
        inicio = perf_counter()
        for tx in comprimidas:
            restaurar_chaves(tx)
        amostras.append(1000 * (perf_counter() - inicio))
    print(f"Bloco: {antes} -> {depois} bytes, economia de {economia} bytes.")
    print(f"Peso: {blocos[0].get_weight()} -> {blocos[1].get_weight()}.")
    print(f"Reconstrução local: mediana {median(amostras):.3f} ms, máximo {max(amostras):.3f} ms.")
    print(f"Tempo nominal de transmissão poupado a 20 Mbit/s: {economia * 8 / 20_000_000:.6f} s.")


def main():
    assinador = Path(__file__).resolve().parents[2] / "build/bin/real26_mldsa65_sign_test"
    chaves = subprocess.check_output([assinador, "gerar"])
    pesos = {}
    for entradas in (1, 2, 3, 5, 10):
        tx = assinar(assinador, chaves, entradas)
        comprimida = comprimir_testemunhas(tx)
        conferir_reconstrucao(tx, comprimida)
        atual, proposto = tx.get_weight(), comprimida.get_weight()
        assert atual - proposto == 1953 * (entradas - 1)
        pesos[entradas] = atual, proposto
        print(f"{entradas:2} entradas  {atual:6} -> {proposto:6} peso  "
              f"economia {atual - proposto:5} bytes ({100 * (atual - proposto) / atual:.2f}% do peso)")

    # Controle de formato. As chaves são reais, e as assinaturas copiadas
    # servem apenas para preservar o tamanho da testemunha nesse controle.
    controle = assinar(assinador, chaves, 3)
    for testemunha in controle.wit.vtxinwit[1:]:
        outra_chave = subprocess.check_output([assinador, "gerar"])[:1952]
        testemunha.scriptWitness.stack[1] = outra_chave
    assert len({w.scriptWitness.stack[1] for w in controle.wit.vtxinwit}) == 3
    comprimida = comprimir_testemunhas(controle)
    conferir_reconstrucao(controle, comprimida)
    assert comprimida.get_weight() == controle.get_weight()
    print("Controle com três chaves distintas  economia zero.")
    print("Projeções de TPS com 4 milhões, 5 minutos e reserva de 1.000 unidades:")
    for percentual in (0, 10, 25, 50, 100):
        resultados = []
        for coluna in (0, 1):
            peso_por_cem = (100 - percentual) * pesos[1][coluna] + percentual * pesos[2][coluna]
            resultados.append((3_999_000 * 100 // peso_por_cem) / 300)
        print(f"{percentual:3}% de transações com duas entradas da mesma chave  "
              f"{resultados[0]:.2f} -> {resultados[1]:.2f} TPS")


    medir_bloco(assinador, chaves)


if __name__ == "__main__":
    main()
