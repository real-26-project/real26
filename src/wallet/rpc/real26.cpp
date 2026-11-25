// Distribuído sob a licença MIT. Consulte o arquivo COPYING.
#include <chainparams.h>
#include <consensus/amount.h>
#include <hash.h>
#include <interfaces/chain.h>
#include <key_io.h>
#include <node/types.h>
#include <policy/policy.h>
#include <random.h>
#include <rpc/protocol.h>
#include <rpc/util.h>
#include <script/descriptor.h>
#include <script/interpreter.h>
#include <script/real26_mldsa65.h>
#include <script/signingprovider.h>
#include <util/strencodings.h>
#include <util/time.h>
#include <wallet/crypter.h>
#include <wallet/rpc/util.h>
#include <wallet/wallet.h>

#include <oqs/oqs.h>

#include <algorithm>
#include <set>
#include <string>
#include <vector>

namespace wallet {
namespace {
const std::string MLDSA65_KEY{"real26mldsa65v1"};

struct Mldsa65Record {
    std::vector<unsigned char> public_key;
    uint256 iv;
    std::vector<unsigned char> ciphertext;

    SERIALIZE_METHODS(Mldsa65Record, obj) { READWRITE(obj.public_key, obj.iv, obj.ciphertext); }
};

void CheckWallet(const CWallet& wallet) EXCLUSIVE_LOCKS_REQUIRED(wallet.cs_wallet)
{
    if (!Params().GetConsensus().real26_mldsa65) throw JSONRPCError(RPC_WALLET_ERROR, "Esta operação requer uma rede REAL-26.");
    if (wallet.IsWalletFlagSet(WALLET_FLAG_DISABLE_PRIVATE_KEYS) || !wallet.HasEncryptionKeys()) {
        throw JSONRPCError(RPC_WALLET_ERROR, "Use uma carteira do Core criptografada e com chaves privadas habilitadas.");
    }
}

std::vector<unsigned char> Mldsa65Program(const Mldsa65Record& record)
{
    if (record.public_key.size() != OQS_SIG_ml_dsa_65_length_public_key) {
        throw JSONRPCError(RPC_WALLET_ERROR, "O registro da chave ML-DSA-65 está inválido.");
    }
    HashWriter hash;
    hash.write(std::as_bytes(std::span{record.public_key}));
    const uint256 digest = hash.GetSHA256();
    return {digest.begin(), digest.end()};
}

Mldsa65Record LoadOrCreate(CWallet& wallet) EXCLUSIVE_LOCKS_REQUIRED(wallet.cs_wallet)
{
    auto batch = wallet.GetDatabase().MakeBatch();
    Mldsa65Record record;
    if (batch->Read(MLDSA65_KEY, record)) return record;

    EnsureWalletIsUnlocked(wallet);
    record.public_key.resize(OQS_SIG_ml_dsa_65_length_public_key);
    record.iv = GetRandHash();
    CKeyingMaterial secret(OQS_SIG_ml_dsa_65_length_secret_key);
    if (OQS_SIG_ml_dsa_65_keypair(record.public_key.data(), secret.data()) != OQS_SUCCESS ||
        !wallet.WithEncryptionKey([&](const CKeyingMaterial& key) {
            return !key.empty() && EncryptSecret(key, secret, record.iv, record.ciphertext);
        }) || !batch->Write(MLDSA65_KEY, record, /*fOverwrite=*/false)) {
        throw JSONRPCError(RPC_WALLET_ERROR, "Não foi possível gerar e persistir a chave ML-DSA-65.");
    }
    return record;
}

void WithReal26Passphrase(CWallet& wallet, const UniValue& parameter,
                         const std::function<void(const CKeyingMaterial&)>& use_key)
{
    const std::string& value = parameter.get_str();
    if (value.empty() || value.find('\0') != std::string::npos) {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "Informe uma senha válida.");
    }
    const SecureString passphrase(value.begin(), value.end());
    if (!wallet.WithPassphraseKey(passphrase, use_key)) {
        throw JSONRPCError(RPC_WALLET_PASSPHRASE_INCORRECT, "A senha da carteira está incorreta.");
    }
}

UniValue SendReal26(CWallet& wallet, std::vector<CTxOut> outputs, CAmount fee, const UniValue& passphrase)
{
    CAmount amount{0};
    for (const auto& output : outputs) {
        if (output.nValue <= 0 || !MoneyRange(amount + output.nValue)) {
            throw JSONRPCError(RPC_INVALID_PARAMETER, "Valor de pagamento inválido.");
        }
        amount += output.nValue;
    }
    if (amount == 0 || fee <= 0 || !MoneyRange(amount + fee) || fee > wallet.m_default_max_tx_fee) {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "Valor ou taxa inválidos.");
    }
    wallet.BlockUntilSyncedToCurrentChain();
    CMutableTransaction tx;
    {
        LOCK(wallet.cs_wallet);
        CheckWallet(wallet);
        if (passphrase.isNull()) EnsureWalletIsUnlocked(wallet);
        Mldsa65Record record;
        if (!wallet.GetDatabase().MakeBatch()->Read(MLDSA65_KEY, record)) {
            throw JSONRPCError(RPC_WALLET_ERROR, "Gere um endereço ML-DSA-65 na carteira primeiro.");
        }
        CKeyingMaterial secret;
        const auto decrypt = [&](const CKeyingMaterial& key) {
            if (key.empty() || !DecryptSecret(key, record.ciphertext, record.iv, secret)) {
                throw JSONRPCError(RPC_WALLET_ERROR, "Não foi possível desbloquear a chave ML-DSA-65.");
            }
        };
        if (passphrase.isNull()) {
            wallet.WithEncryptionKey([&](const CKeyingMaterial& key) { decrypt(key); return true; });
        } else {
            WithReal26Passphrase(wallet, passphrase, decrypt);
        }
        const CScript origin = GetScriptForDestination(WitnessUnknown{2, Mldsa65Program(record)});
        std::vector<std::pair<COutPoint, CTxOut>> coins;
        for (const auto& [id, entry] : wallet.mapWallet) {
            if (wallet.GetTxDepthInMainChain(entry) <= 0 || wallet.GetTxBlocksToMaturity(entry) > 0) continue;
            const auto current = entry.GetTx();
            for (uint32_t i = 0; i < current->vout.size(); ++i) {
                const COutPoint outpoint{id, i};
                const auto& output = current->vout[i];
                if (output.scriptPubKey == origin && !wallet.IsSpent(outpoint) && !wallet.IsLockedCoin(outpoint)) {
                    coins.emplace_back(outpoint, output);
                }
            }
        }
        std::ranges::sort(coins, [](const auto& a, const auto& b) {
            if (a.second.nValue != b.second.nValue) return a.second.nValue > b.second.nValue;
            return a.first < b.first;
        });
        std::vector<CTxOut> prevouts;
        CAmount total{0};
        for (const auto& [outpoint, output] : coins) {
            tx.vin.emplace_back(outpoint);
            prevouts.push_back(output);
            total += output.nValue;
            if (total >= amount + fee) break;
        }
        if (total < amount + fee) throw JSONRPCError(RPC_WALLET_INSUFFICIENT_FUNDS, "Saldo ML-DSA-65 confirmado e maduro insuficiente.");
        tx.vout = std::move(outputs);
        if (const auto change = total - amount - fee; change > 0) tx.vout.emplace_back(change, origin);

        constexpr size_t witness_weight{1 + 3 + OQS_SIG_ml_dsa_65_length_signature +
                                        3 + OQS_SIG_ml_dsa_65_length_public_key};
        if (GetSerializeSize(TX_NO_WITNESS(tx)) * 4 + 2 + tx.vin.size() * witness_weight > MAX_STANDARD_TX_WEIGHT) {
            throw JSONRPCError(RPC_WALLET_ERROR, "O gasto ML-DSA-65 excede o peso padrão de uma transação.");
        }
        PrecomputedTransactionData data;
        data.Init(tx, std::move(prevouts), /*force=*/true);
        for (unsigned int i = 0; i < tx.vin.size(); ++i) {
            if (!SignReal26Mldsa65Input(tx, i, data, record.public_key, secret, Params().GetConsensus().hashGenesisBlock)) {
                throw JSONRPCError(RPC_WALLET_ERROR, "Falha ao assinar o gasto ML-DSA-65.");
            }
        }
    }

    const auto signed_tx = MakeTransactionRef(std::move(tx));
    std::string error;
    if (!wallet.chain().broadcastTransaction(signed_tx, wallet.m_default_max_tx_fee,
            node::TxBroadcast::MEMPOOL_AND_BROADCAST_TO_ALL, error)) {
        throw JSONRPCError(RPC_WALLET_ERROR, error);
    }
    return signed_tx->GetHash().ToString();
}
} // namespace

RPCMethod getreal26address()
{
    return RPCMethod{"getreal26address",
        "Cria ou retorna o endereço ML-DSA-65 da carteira REAL-26 criptografada.",
        {},
        RPCResult{RPCResult::Type::STR, "endereco", "Endereço ML-DSA-65 de desenvolvimento."},
        RPCExamples{HelpExampleCli("getreal26address", "")},
        [](const RPCMethod&, const JSONRPCRequest& request) -> UniValue {
            auto wallet = GetWalletForJSONRPCRequest(request);
            if (!wallet) return UniValue::VNULL;
            LOCK(wallet->cs_wallet);
            CheckWallet(*wallet);
            const Mldsa65Record record = LoadOrCreate(*wallet);
            const auto program = Mldsa65Program(record);
            const std::string address = EncodeDestination(WitnessUnknown{2, program});
            FlatSigningProvider provider;
            std::string error;
            auto parsed = Parse("addr(" + address + ")", provider, error);
            if (parsed.size() != 1) throw JSONRPCError(RPC_WALLET_ERROR, "Não foi possível interpretar o endereço ML-DSA-65.");
            WalletDescriptor descriptor{std::move(parsed.front()), static_cast<uint64_t>(GetTime()), 0, 1, 0};
            if (!wallet->GetDescriptorScriptPubKeyMan(descriptor) &&
                !wallet->AddWalletDescriptor(descriptor, provider, "REAL-26 ML-DSA-65", /*internal=*/false)) {
                throw JSONRPCError(RPC_WALLET_ERROR, "Não foi possível registrar o endereço ML-DSA-65 na carteira.");
            }
            return address;
        }};
}

RPCMethod sendreal26()
{
    return RPCMethod{"sendreal26",
        "Seleciona moedas ML-DSA-65 confirmadas, assina e envia na rede REAL-26.",
        {
            {"address", RPCArg::Type::STR, RPCArg::Optional::NO, "Endereço de destino."},
            {"amount", RPCArg::Type::AMOUNT, RPCArg::Optional::NO, "Valor em moedas."},
            {"fee", RPCArg::Type::AMOUNT, RPCArg::Optional::NO, "Taxa total em moedas."},
            {"passphrase", RPCArg::Type::STR, RPCArg::Optional::OMITTED, "Autoriza somente este pagamento, sem desbloquear a carteira."},
        },
        RPCResult{RPCResult::Type::STR_HEX, "txid", "Identificador do pagamento."},
        RPCExamples{HelpExampleCli("sendreal26", "ENDERECO 1.0 0.0001")},
        [](const RPCMethod&, const JSONRPCRequest& request) -> UniValue {
            auto wallet = GetWalletForJSONRPCRequest(request);
            if (!wallet) return UniValue::VNULL;
            const auto destination = DecodeDestination(request.params[0].get_str());
            const auto script = GetScriptForDestination(destination);
            if (!IsReal26Mldsa65Script(script)) {
                throw JSONRPCError(RPC_INVALID_ADDRESS_OR_KEY, "O pagamento exige endereços ML-DSA-65.");
            }
            const CAmount amount = AmountFromValue(request.params[1]);
            const CAmount fee = AmountFromValue(request.params[2]);
            return SendReal26(*wallet, {CTxOut{amount, script}}, fee, request.params[3]);
        }};
}
RPCMethod sendreal26many()
{
    return RPCMethod{"sendreal26many",
        "Paga vários endereços ML-DSA-65 em uma transação da rede REAL-26.",
        {
            {"amounts", RPCArg::Type::OBJ_USER_KEYS, RPCArg::Optional::NO, "Endereços e valores.",
                {
                    {"address", RPCArg::Type::AMOUNT, RPCArg::Optional::NO, "Endereço como chave e valor em moedas."},
                }},
            {"fee", RPCArg::Type::AMOUNT, RPCArg::Optional::NO, "Taxa total em moedas."},
            {"passphrase", RPCArg::Type::STR, RPCArg::Optional::OMITTED, "Autoriza somente este lote, sem desbloquear a carteira."},
        },
        RPCResult{RPCResult::Type::STR_HEX, "txid", "Identificador da transação."},
        RPCExamples{HelpExampleCli("sendreal26many", "'{\"ENDERECO1\":1.0,\"ENDERECO2\":2.0}' 0.0001")},
        [](const RPCMethod&, const JSONRPCRequest& request) -> UniValue {
            auto wallet = GetWalletForJSONRPCRequest(request);
            if (!wallet) return UniValue::VNULL;
            const auto& amounts = request.params[0].get_obj();
            const auto& keys = amounts.getKeys();
            const auto& values = amounts.getValues();
            std::set<CScript> used;
            std::vector<CTxOut> outputs;
            for (size_t i = 0; i < keys.size(); ++i) {
                const auto destination = DecodeDestination(keys[i]);
                const auto script = GetScriptForDestination(destination);
                if (!IsReal26Mldsa65Script(script)) {
                    throw JSONRPCError(RPC_INVALID_ADDRESS_OR_KEY, "O lote exige endereços ML-DSA-65.");
                }
                if (!used.insert(script).second) {
                    throw JSONRPCError(RPC_INVALID_PARAMETER, "Endereço duplicado no lote.");
                }
                outputs.emplace_back(AmountFromValue(values[i]), script);
            }
            return SendReal26(*wallet, std::move(outputs), AmountFromValue(request.params[1]), request.params[2]);
        }};
}

RPCMethod verifyreal26passphrase()
{
    return RPCMethod{"verifyreal26passphrase", "Valida a senha sem desbloquear a carteira REAL-26.",
        {{"passphrase", RPCArg::Type::STR, RPCArg::Optional::NO, "Senha da carteira."}},
        RPCResult{RPCResult::Type::BOOL, "valid", "Verdadeiro quando a senha está correta."},
        RPCExamples{""},
        [](const RPCMethod&, const JSONRPCRequest& request) -> UniValue {
            auto wallet = GetWalletForJSONRPCRequest(request);
            if (!wallet) return UniValue::VNULL;
            LOCK(wallet->cs_wallet);
            CheckWallet(*wallet);
            WithReal26Passphrase(*wallet, request.params[0], [](const CKeyingMaterial&) {});
            return true;
        }};
}
} // namespace wallet
