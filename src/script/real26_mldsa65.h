// Distribuído sob a licença MIT. Consulte o arquivo COPYING.
#ifndef BITCOIN_SCRIPT_REAL26_MLDSA65_H
#define BITCOIN_SCRIPT_REAL26_MLDSA65_H

#include <script/script.h>
#include <uint256.h>

#include <span>

class CMutableTransaction;
class PrecomputedTransactionData;
// Domínios distintos impedem a reutilização de assinaturas entre as redes.
inline const uint256 REAL26_DEV_GENESIS{"26df5874074ef2b195f095a7f38d13db0dbf22e11b4ab1b22d881303fc408905"};
inline const uint256 REAL26_TEST_GENESIS{"000f21da01c7bb9dfb2a2e1c441c1b22587639216626312523249fc990eceaa4"};

inline const uint256 REAL26_REFS_GENESIS{"3259f716dc16d1f59dd6b05a245a5ac268a1c8bc788e3304878bc0a0bc873405"};

inline const uint256 REAL26_TEST_REFS_GENESIS{"00008e6fbebecfe46f33a0ef6c0655cde4d796bb4638d21bf858b434d9e2e7ed"};

inline const uint256 REAL26_ENSAIO_GENESIS{"0007326bf77a1489a5e6ee7aa98affe5baac14aa7f2b694a86e2b54c8ae24733"};
inline const uint256 REAL26_ASERT_GENESIS{"0145759a8518385c134aa276159d91dc321a6cbd958156b617ce5845bad9fad8"};
inline const uint256 REAL26_TEST_ASERT_GENESIS{"0000058319331d5a63c4d88f6338cce3b9deb43110246e701b4508dc4c15b2c2"};

inline bool IsReal26Mldsa65Script(const CScript& script)
{
    return script.size() == 34 && script[0] == OP_2 && script[1] == 32;
}

bool Real26Mldsa65SignatureHash(uint256& sighash, const CMutableTransaction& tx,
                              unsigned int input, const PrecomputedTransactionData& data);

bool SignReal26Mldsa65Input(CMutableTransaction& tx, unsigned int input, const PrecomputedTransactionData& data,
                           std::span<const unsigned char> public_key, std::span<const unsigned char> secret_key, const uint256& genesis = REAL26_DEV_GENESIS);

#endif // BITCOIN_SCRIPT_REAL26_MLDSA65_H
