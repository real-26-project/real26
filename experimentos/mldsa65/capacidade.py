# Distribuído sob a licença MIT. Consulte COPYING.
"""Mede o peso serializado de pagamentos ML-DSA-65 assinados localmente."""
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

import carteira
from test_framework.messages import COIN, COutPoint, CTransaction, CTxIn, CTxOut


def medir(pagamentos, publica, arquivo, senha, assinador):
    origem = b"\x52\x20" + carteira.compromisso(publica)
    anterior = CTxOut(COIN, origem)
    valor = 100_000
    taxa = 10_000
    tx = CTransaction()
    tx.version = 2
    tx.vin = [CTxIn(COutPoint(1, 0))]
    for indice in range(pagamentos):
        # Compromissos fictícios distintos para medir o formato sem gastar moedas.
        compromisso = hashlib.sha256(indice.to_bytes(4, "little")).digest()
        tx.vout.append(CTxOut(valor, b"\x52\x20" + compromisso))
    tx.vout.append(CTxOut(anterior.nValue - pagamentos * valor - taxa, origem))
    carteira.assinar_com_arquivo(tx, [anterior], arquivo, senha, assinador)
    tamanho = len(tx.serialize())
    peso = 3 * len(tx.serialize_without_witness()) + tamanho
    return tamanho, peso


if __name__ == "__main__":
    assinador = carteira.RAIZ / "build/bin/real26_mldsa65_sign_test"
    with TemporaryDirectory() as pasta:
        arquivo = Path(pasta) / "carteira-teste.enc"
        senha = "senha temporária de laboratório"
        publica = carteira.criar_carteira(arquivo, senha, assinador)
        for pagamentos in (1, 10, 100):
            tamanho, peso = medir(pagamentos, publica, arquivo, senha, assinador)
            print(f"{pagamentos} destinatário(s): {tamanho} bytes e {peso} unidades de peso")
            for limite, intervalo in ((4_000_000, 600), (10_000_000, 300), (15_000_000, 300)):
                # Reserva 1.000 unidades para cabeçalho, contagem e coinbase ilustrativa.
                por_bloco = (limite - 1_000) // peso
                print(f"  {limite:,} unidades, {intervalo} s: {por_bloco} transações/bloco, "
                      f"{por_bloco / intervalo:.2f} TPS, "
                      f"{pagamentos * por_bloco / intervalo:.2f} pagamentos/s")
