# Distribuído sob a licença MIT. Consulte COPYING.
"""Valida a codificação das mensagens propostas para a coinbase do gênese."""
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO

from test_framework.messages import CBlock, COutPoint, CTransaction, CTxIn, CTxOut, tx_from_hex
from test_framework.script import CScript, CScriptNum, OP_RETURN


MENSAGEM_CURTA = "Brasil soberano, povo livre. Nossa voz, nosso trabalho e nosso futuro nos pertencem."
MENSAGEM_LONGA = (
    "Queremos um Brasil soberano, onde ninguém tema falar, onde cada pessoa possa guardar o fruto "
    "do seu trabalho e onde todo poder responda ao povo. A liberdade é o direito de decidir o próprio futuro."
)


def montar_coinbase():
    curta = MENSAGEM_CURTA.encode("utf-8")
    longa = MENSAGEM_LONGA.encode("utf-8")
    script_curto = CScript([486604799, CScriptNum(4), curta])
    script_longo = CScript([486604799, CScriptNum(4), longa])
    assert len(script_curto) <= 100 < len(script_longo)

    coinbase = CTransaction()
    coinbase.version = 1
    coinbase.vin = [CTxIn(COutPoint(0, 0xffffffff), script_curto, 0xffffffff)]
    coinbase.vout = [CTxOut(0, CScript([OP_RETURN, longa]))]
    serializada = coinbase.serialize()
    reaberta = tx_from_hex(serializada.hex())
    assert list(CScript(reaberta.vin[0].scriptSig))[-1] == curta
    assert (reaberta.vin[0].prevout.hash, reaberta.vin[0].prevout.n) == (0, 0xffffffff)
    assert reaberta.vout[0].nValue == 0
    assert list(CScript(reaberta.vout[0].scriptPubKey)) == [OP_RETURN, longa]
    print(f"Mensagem curta: {len(curta)} bytes. Na coinbase: {len(script_curto)} bytes de scriptSig.")
    print(f"Mensagem longa: {len(longa)} bytes. Na coinbase: {len(script_longo)} bytes de scriptSig.")
    print(f"Mensagem longa em OP_RETURN: {len(reaberta.vout[0].scriptPubKey)} bytes de script.")
    print(f"SHA-256 da mensagem longa: {sha256(longa).hexdigest()}")
    return coinbase


def minerar_genese_de_ensaio():
    bloco = CBlock()
    bloco.nVersion = 1
    bloco.nTime = int(datetime(2026, 11, 20, tzinfo=timezone.utc).timestamp())
    bloco.nBits = 0x1f0fffff  # Alvo da testnet, reservado ao ensaio.
    bloco.vtx = [montar_coinbase()]
    bloco.hashMerkleRoot = bloco.calc_merkle_root()
    bloco.solve()
    reaberto = CBlock()
    reaberto.deserialize(BytesIO(bloco.serialize()))
    assert reaberto.hashPrevBlock == 0
    assert reaberto.is_valid()
    assert len(reaberto.vtx) == 1 and reaberto.vtx[0].serialize() == bloco.vtx[0].serialize()
    assert reaberto.hash_hex == sha256(sha256(bloco.serialize()[:80]).digest()).digest()[::-1].hex()
    print(f"Genese de ensaio: {reaberto.hash_hex}")
    print(f"Raiz de Merkle:    {reaberto.hashMerkleRoot:064x}")
    print(f"Timestamp: {reaberto.nTime}; nBits: {reaberto.nBits:08x}; nonce: {reaberto.nNonce}")


if __name__ == "__main__":
    minerar_genese_de_ensaio()
