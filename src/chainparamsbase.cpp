// Copyright (c) 2010 Satoshi Nakamoto
// Copyright (c) 2009-present The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <chainparamsbase.h>

#include <common/args.h>
#include <tinyformat.h>
#include <util/chaintype.h>

#include <cassert>
#include <stdexcept>

void SetupChainParamsBaseOptions(ArgsManager& argsman)
{
    argsman.AddArg("-chain=<chain>", "Use the chain <chain> (default: main). Allowed values: " LIST_CHAIN_NAMES, ArgsManager::ALLOW_ANY, OptionsCategory::CHAINPARAMS);
    argsman.AddArg("-regtest", "Enter regression test mode, which uses a special chain in which blocks can be solved instantly. "
                 "This is intended for regression testing tools and app development. Equivalent to -chain=regtest.", ArgsManager::ALLOW_ANY | ArgsManager::DEBUG_ONLY, OptionsCategory::CHAINPARAMS);
    argsman.AddArg("-real26test", "Usa a testnet isolada da REAL-26. Requer -testnet4.", ArgsManager::ALLOW_ANY, OptionsCategory::CHAINPARAMS);
    argsman.AddArg("-real26ensaio", "Usa a rede privada de ensaio da REAL-26. Requer -testnet4 -real26test -real26testrefs.", ArgsManager::ALLOW_ANY, OptionsCategory::CHAINPARAMS);
    argsman.AddArg("-real26testasert", "Usa a testnet compartilhada ASERT. Requer -testnet4 -real26test -real26testrefs.", ArgsManager::ALLOW_ANY, OptionsCategory::CHAINPARAMS);
    argsman.AddArg("-real26testrefs", "Usa a testnet REAL-26 com referências ML-DSA-65. Requer -testnet4 -real26test.", ArgsManager::ALLOW_ANY, OptionsCategory::CHAINPARAMS);
    argsman.AddArg("-real26refs", "Habilita o laboratório de referências ML-DSA-65. Requer -regtest -real26dev.", ArgsManager::ALLOW_ANY | ArgsManager::DEBUG_ONLY, OptionsCategory::CHAINPARAMS);
    argsman.AddArg("-real26dev", "Usa a rede de desenvolvimento isolada da REAL-26. Requer -regtest.", ArgsManager::ALLOW_ANY, OptionsCategory::CHAINPARAMS);
    argsman.AddArg("-real26asert", "Usa o laboratório de prova de trabalho ASERT. Requer -regtest.", ArgsManager::ALLOW_ANY | ArgsManager::DEBUG_ONLY, OptionsCategory::CHAINPARAMS);
    argsman.AddArg("-testactivationheight=name@height.", "Set the activation height of 'name' (segwit, bip34, dersig, cltv, csv). (test-only)", ArgsManager::ALLOW_ANY | ArgsManager::DEBUG_ONLY, OptionsCategory::DEBUG_TEST);
    argsman.AddArg("-testnet", "Use the testnet3 chain. Equivalent to -chain=test. Support for testnet3 is deprecated and will be removed in an upcoming release. Consider moving to testnet4 now by using -testnet4.", ArgsManager::ALLOW_ANY, OptionsCategory::CHAINPARAMS);
    argsman.AddArg("-testnet4", "Use the testnet4 chain. Equivalent to -chain=testnet4.", ArgsManager::ALLOW_ANY, OptionsCategory::CHAINPARAMS);
    argsman.AddArg("-vbparams=deployment:start:end[:min_activation_height]", "Use given start/end times and min_activation_height for specified version bits deployment (test-only)", ArgsManager::ALLOW_ANY | ArgsManager::DEBUG_ONLY, OptionsCategory::CHAINPARAMS);
    argsman.AddArg("-signet", "Use the signet chain. Equivalent to -chain=signet. Note that the network is defined by the -signetchallenge parameter", ArgsManager::ALLOW_ANY, OptionsCategory::CHAINPARAMS);
    argsman.AddArg("-signetchallenge", "Blocks must satisfy the given script to be considered valid (only for signet networks; defaults to the global default signet test network challenge)", ArgsManager::ALLOW_ANY | ArgsManager::DISALLOW_NEGATION, OptionsCategory::CHAINPARAMS);
    argsman.AddArg("-signetseednode", "Specify a seed node for the signet network, in the hostname[:port] format, e.g. sig.net:1234 (may be used multiple times to specify multiple seed nodes; defaults to the global default signet test network seed node(s))", ArgsManager::ALLOW_ANY | ArgsManager::DISALLOW_NEGATION, OptionsCategory::CHAINPARAMS);
}

static std::unique_ptr<CBaseChainParams> globalChainBaseParams;

const CBaseChainParams& BaseParams()
{
    assert(globalChainBaseParams);
    return *globalChainBaseParams;
}

/**
 * Port numbers for incoming Tor connections (8334, 18334, 38334, 48334, 18445) have
 * been chosen arbitrarily to keep ranges of used ports tight.
 */
std::unique_ptr<CBaseChainParams> CreateBaseChainParams(const ChainType chain)
{
    switch (chain) {
    case ChainType::MAIN:
        return std::make_unique<CBaseChainParams>("", 8332);
    case ChainType::TESTNET:
        return std::make_unique<CBaseChainParams>("testnet3", 18332);
    case ChainType::TESTNET4:
        return std::make_unique<CBaseChainParams>("testnet4", 48332);
    case ChainType::SIGNET:
        return std::make_unique<CBaseChainParams>("signet", 38332);
    case ChainType::REGTEST:
        return std::make_unique<CBaseChainParams>("regtest", 18443);
    }
    assert(false);
}

void SelectBaseParams(const ChainType chain)
{
    gArgs.SelectConfigNetwork(ChainTypeToString(chain));
    const bool real26_dev = gArgs.GetBoolArg("-real26dev", false);
    const bool real26_refs = gArgs.GetBoolArg("-real26refs", false);
    if (real26_refs && (!real26_dev || chain != ChainType::REGTEST)) {
        throw std::runtime_error("-real26refs requer -regtest -real26dev.");
    }
    const bool real26_test = gArgs.GetBoolArg("-real26test", false);
    const bool real26_test_refs = gArgs.GetBoolArg("-real26testrefs", false);
    const bool real26_ensaio = gArgs.GetBoolArg("-real26ensaio", false);
    const bool real26_test_asert = gArgs.GetBoolArg("-real26testasert", false);
    if (real26_test_asert && (!real26_test_refs || real26_ensaio)) {
        throw std::runtime_error("-real26testasert requer -testnet4 -real26test -real26testrefs e exclui -real26ensaio.");
    }
    const bool real26_asert = gArgs.GetBoolArg("-real26asert", false);
    if (real26_asert && (chain != ChainType::REGTEST || real26_refs || real26_test || real26_test_refs || real26_ensaio)) {
        throw std::runtime_error("-real26asert requer -regtest. Use -real26dev para habilitar ML-DSA-65 no laboratório.");
    }
    if (real26_ensaio && !real26_test_refs) {
        throw std::runtime_error("-real26ensaio requer -testnet4 -real26test -real26testrefs.");
    }
    if (real26_test_refs && (!real26_test || chain != ChainType::TESTNET4)) {
        throw std::runtime_error("-real26testrefs requer -testnet4 -real26test.");
    }
    if (real26_dev && real26_test) {
        throw std::runtime_error("Escolha apenas um modo da REAL-26.");
    }
#ifdef REAL26_BENCH_15M
    if (chain != ChainType::REGTEST || !real26_dev || real26_refs || real26_asert) {
        throw std::runtime_error("Este binário de medição requer -regtest -real26dev.");
    }
#endif
    if (real26_asert) {
#ifndef REAL26_EXPERIMENTAL_MLDSA65
        if (real26_dev) throw std::runtime_error("Esta compilação não inclui o suporte ML-DSA-65 exigido por -real26dev.");
#endif
        globalChainBaseParams = real26_dev ? std::make_unique<CBaseChainParams>("real26asert-pq", 29835)
                                          : std::make_unique<CBaseChainParams>("real26asert-lab", 29833);
        return;
    }
    if (real26_test) {
        if (chain != ChainType::TESTNET4) {
            throw std::runtime_error("-real26test requer -testnet4.");
        }
#ifndef REAL26_EXPERIMENTAL_MLDSA65
        throw std::runtime_error("Esta compilação não inclui o suporte ML-DSA-65 exigido por -real26test.");
#endif
        if (gArgs.IsArgSet("-testactivationheight") || gArgs.IsArgSet("-vbparams")) {
            throw std::runtime_error("A testnet REAL-26 usa regras de ativação fixas.");
        }
        if (real26_ensaio) {
            globalChainBaseParams = std::make_unique<CBaseChainParams>("real26ensaio", 29793);
            return;
        }
        if (real26_test_asert) {
            globalChainBaseParams = std::make_unique<CBaseChainParams>("real26testasert-v2", 29837);
            return;
        }
        globalChainBaseParams = real26_test_refs ? std::make_unique<CBaseChainParams>("real26testrefs", 29783)
                                                : std::make_unique<CBaseChainParams>("real26testnet", 29763);
        return;
    }
    if (real26_dev) {
        if (chain != ChainType::REGTEST) {
            throw std::runtime_error("-real26dev requer -regtest.");
        }
#ifndef REAL26_EXPERIMENTAL_MLDSA65
        throw std::runtime_error("Esta compilação não inclui o suporte ML-DSA-65 exigido por -real26dev.");
#endif
#ifdef REAL26_BENCH_15M
        globalChainBaseParams = std::make_unique<CBaseChainParams>("real26bench15m-pq", 29753);
#else
        globalChainBaseParams = real26_refs ? std::make_unique<CBaseChainParams>("real26refs-v2", 29773)
                                           : std::make_unique<CBaseChainParams>("real26mldsa-pq", 29743);
#endif
        return;
    }
    globalChainBaseParams = CreateBaseChainParams(chain);
}
