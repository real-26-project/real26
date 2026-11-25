// Copyright (c) 2009-2010 Satoshi Nakamoto
// Copyright (c) 2009-present The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <pow.h>

#include <arith_uint256.h>
#include <chain.h>
#include <primitives/block.h>
#include <uint256.h>
#include <util/check.h>

#include <algorithm>

static void ScaleDifficultyTarget(arith_uint256& target, int64_t elapsed, const Consensus::Params& params)
{
    const int64_t period = params.nPowTargetTimespan;
    if (!params.real26_testnet) {
        target *= elapsed;
        target /= period;
        return;
    }

    // Na testnet REAL-26, o alvo de até 252 bits pode transbordar se for
    // multiplicado antes da divisão. O quociente cresce no máximo quatro vezes.
    arith_uint256 quotient = target;
    quotient /= period;
    const uint64_t remainder = (target - quotient * period).GetLow64();
    target = quotient * elapsed + (remainder * elapsed) / period;
}

// ASERT inteiro com a âncora definida nas regras da rede (aserti3-2d).
static unsigned int Real26AsertTarget(const CBlockIndex& ultimo, const Consensus::Params& params)
{
    if (ultimo.nHeight < params.real26_asert_anchor_height) {
        return params.real26_asert_initial_bits;
    }
    const CBlockIndex& ancora = *Assert(ultimo.GetAncestor(params.real26_asert_anchor_height));
    const int64_t atraso = ultimo.GetBlockTime() - ancora.GetBlockTime() -
                           (ultimo.nHeight - ancora.nHeight) * params.nPowTargetSpacing;
    const int64_t expoente = atraso * 65536 / params.real26_asert_half_life;
    const int64_t deslocamento = expoente >> 16;
    const uint64_t fracao = static_cast<uint16_t>(expoente);
    const uint32_t fator = 65536 + ((195766423245049ULL * fracao +
        971821376ULL * fracao * fracao + 5127ULL * fracao * fracao * fracao + (1ULL << 47)) >> 48);

    const arith_uint256 limite = UintToArith256(params.powLimit);
    arith_uint256 alvo;
    alvo.SetCompact(ancora.nBits);
    // O alvo inicial da rede permite dividir antes da multiplicação sem arredondar.
    assert((alvo.GetLow64() & 0xffff) == 0 && alvo.bits() <= 255);
    alvo >>= 16;
    alvo *= fator;
    if (deslocamento >= 0) {
        if (deslocamento + alvo.bits() > 256) return limite.GetCompact();
        alvo <<= deslocamento;
    } else {
        if (deslocamento <= -256) return arith_uint256{1}.GetCompact();
        alvo >>= -deslocamento;
    }
    if (alvo == 0) return arith_uint256{1}.GetCompact();
    return std::min(alvo, limite).GetCompact();
}

unsigned int GetNextWorkRequired(const CBlockIndex* pindexLast, const CBlockHeader *pblock, const Consensus::Params& params)
{
    assert(pindexLast != nullptr);
    if (params.real26_asert_half_life > 0) return Real26AsertTarget(*pindexLast, params);
    unsigned int nProofOfWorkLimit = UintToArith256(params.powLimit).GetCompact();

    // Only change once per difficulty adjustment interval
    if ((pindexLast->nHeight+1) % params.DifficultyAdjustmentInterval() != 0)
    {
        if (params.fPowAllowMinDifficultyBlocks)
        {
            // Special difficulty rule for testnet:
            // If the new block's timestamp is more than 2* 10 minutes
            // then it MUST be a min-difficulty block.
            if (pblock->GetBlockTime() > pindexLast->GetBlockTime() + params.nPowTargetSpacing*2)
                return nProofOfWorkLimit;
            else
            {
                // Return the last non-special-min-difficulty-rules-block
                const CBlockIndex* pindex = pindexLast;
                while (pindex->pprev && pindex->nHeight % params.DifficultyAdjustmentInterval() != 0 && pindex->nBits == nProofOfWorkLimit)
                    pindex = pindex->pprev;
                return pindex->nBits;
            }
        }
        return pindexLast->nBits;
    }

    // Go back by what we want to be 14 days worth of blocks
    int nHeightFirst = pindexLast->nHeight - (params.DifficultyAdjustmentInterval()-1);
    assert(nHeightFirst >= 0);
    const CBlockIndex* pindexFirst = pindexLast->GetAncestor(nHeightFirst);
    assert(pindexFirst);

    return CalculateNextWorkRequired(pindexLast, pindexFirst->GetBlockTime(), params);
}

unsigned int CalculateNextWorkRequired(const CBlockIndex* pindexLast, int64_t nFirstBlockTime, const Consensus::Params& params)
{
    if (params.fPowNoRetargeting)
        return pindexLast->nBits;

    // Limit adjustment step
    int64_t nActualTimespan = pindexLast->GetBlockTime() - nFirstBlockTime;
    if (nActualTimespan < params.nPowTargetTimespan/4)
        nActualTimespan = params.nPowTargetTimespan/4;
    if (nActualTimespan > params.nPowTargetTimespan*4)
        nActualTimespan = params.nPowTargetTimespan*4;

    // Retarget
    const arith_uint256 bnPowLimit = UintToArith256(params.powLimit);
    arith_uint256 bnNew;

    // Special difficulty rule for Testnet4
    if (params.enforce_BIP94) {
        // Here we use the first block of the difficulty period. This way
        // the real difficulty is always preserved in the first block as
        // it is not allowed to use the min-difficulty exception.
        int nHeightFirst = pindexLast->nHeight - (params.DifficultyAdjustmentInterval()-1);
        const CBlockIndex* pindexFirst = pindexLast->GetAncestor(nHeightFirst);
        bnNew.SetCompact(pindexFirst->nBits);
    } else {
        bnNew.SetCompact(pindexLast->nBits);
    }

    ScaleDifficultyTarget(bnNew, nActualTimespan, params);

    if (bnNew > bnPowLimit)
        bnNew = bnPowLimit;

    return bnNew.GetCompact();
}

// Check that on difficulty adjustments, the new difficulty does not increase
// or decrease beyond the permitted limits.
bool PermittedDifficultyTransition(const Consensus::Params& params, int64_t height, uint32_t old_nbits, uint32_t new_nbits)
{
    // A pré-sincronização só tem dois alvos. A validação contextual confere o ASERT exato.
    if (params.real26_asert_half_life > 0) return DeriveTarget(new_nbits, params.powLimit).has_value();
    if (params.fPowAllowMinDifficultyBlocks) return true;

    if (height % params.DifficultyAdjustmentInterval() == 0) {
        int64_t smallest_timespan = params.nPowTargetTimespan/4;
        int64_t largest_timespan = params.nPowTargetTimespan*4;

        const arith_uint256 pow_limit = UintToArith256(params.powLimit);
        arith_uint256 observed_new_target;
        observed_new_target.SetCompact(new_nbits);

        // Calculate the largest difficulty value possible:
        arith_uint256 largest_difficulty_target;
        largest_difficulty_target.SetCompact(old_nbits);
        ScaleDifficultyTarget(largest_difficulty_target, largest_timespan, params);

        if (largest_difficulty_target > pow_limit) {
            largest_difficulty_target = pow_limit;
        }

        // Round and then compare this new calculated value to what is
        // observed.
        arith_uint256 maximum_new_target;
        maximum_new_target.SetCompact(largest_difficulty_target.GetCompact());
        if (maximum_new_target < observed_new_target) return false;

        // Calculate the smallest difficulty value possible:
        arith_uint256 smallest_difficulty_target;
        smallest_difficulty_target.SetCompact(old_nbits);
        ScaleDifficultyTarget(smallest_difficulty_target, smallest_timespan, params);

        if (smallest_difficulty_target > pow_limit) {
            smallest_difficulty_target = pow_limit;
        }

        // Round and then compare this new calculated value to what is
        // observed.
        arith_uint256 minimum_new_target;
        minimum_new_target.SetCompact(smallest_difficulty_target.GetCompact());
        if (minimum_new_target > observed_new_target) return false;
    } else if (old_nbits != new_nbits) {
        return false;
    }
    return true;
}

// Bypasses the actual proof of work check during fuzz testing with a simplified validation checking whether
// the most significant bit of the last byte of the hash is set.
bool CheckProofOfWork(uint256 hash, unsigned int nBits, const Consensus::Params& params)
{
    if (EnableFuzzDeterminism()) return (hash.data()[31] & 0x80) == 0;
    return CheckProofOfWorkImpl(hash, nBits, params);
}

std::optional<arith_uint256> DeriveTarget(unsigned int nBits, const uint256 pow_limit)
{
    bool fNegative;
    bool fOverflow;
    arith_uint256 bnTarget;

    bnTarget.SetCompact(nBits, &fNegative, &fOverflow);

    // Check range
    if (fNegative || bnTarget == 0 || fOverflow || bnTarget > UintToArith256(pow_limit))
        return {};

    return bnTarget;
}

bool CheckProofOfWorkImpl(uint256 hash, unsigned int nBits, const Consensus::Params& params)
{
    auto bnTarget{DeriveTarget(nBits, params.powLimit)};
    if (!bnTarget) return false;

    // Check proof of work matches claimed amount
    if (UintToArith256(hash) > bnTarget)
        return false;

    return true;
}
