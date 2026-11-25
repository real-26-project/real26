// Distribuído sob a licença MIT. Consulte o arquivo COPYING.
#include <consensus/amount.h>
#include <crypto/common.h>
#include <hash.h>
#include <policy/policy.h>
#include <primitives/transaction.h>
#include <script/interpreter.h>
#include <script/real26_mldsa65.h>
#include <streams.h>
#include <support/allocators/secure.h>

#include <oqs/oqs.h>
#include <openssl/evp.h>
#include <openssl/rand.h>

#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <set>
#include <span>
#include <stdexcept>
#include <string_view>
#include <vector>

namespace {
using SecureBytes = std::vector<unsigned char, secure_allocator<unsigned char>>;
using CipherContext = std::unique_ptr<EVP_CIPHER_CTX, decltype(&EVP_CIPHER_CTX_free)>;
constexpr std::string_view WALLET_FORMAT{"REAL26-CARTEIRA-2"};
constexpr size_t SALT_SIZE{16}, NONCE_SIZE{12}, TAG_SIZE{16};
constexpr size_t PUBLIC_SIZE{OQS_SIG_ml_dsa_65_length_public_key};
constexpr size_t SECRET_SIZE{OQS_SIG_ml_dsa_65_length_secret_key};
constexpr size_t BODY_SIZE{PUBLIC_SIZE + SECRET_SIZE};
constexpr size_t HEADER_SIZE{WALLET_FORMAT.size() + SALT_SIZE + NONCE_SIZE};
using Envelope = std::array<unsigned char, HEADER_SIZE + BODY_SIZE + TAG_SIZE>;

void ReadExact(std::span<unsigned char> data)
{
    if (std::fread(data.data(), 1, data.size(), stdin) != data.size()) {
        throw std::runtime_error("Dados de entrada incompletos.");
    }
}

SecureBytes ReadPassword()
{
    // A senha é precedida por seu tamanho em LE32 no canal local.
    std::array<unsigned char, 4> password_length{};
    ReadExact(password_length);
    const size_t length = ReadLE32(password_length.data());
    if (length == 0 || length > 1024 * 1024) throw std::runtime_error("Tamanho de senha inválido.");
    SecureBytes password(length);
    ReadExact(password);
    return password;
}

SecureBytes DeriveKey(const SecureBytes& password, const Envelope& envelope)
{
    SecureBytes key(32);
    if (EVP_PBE_scrypt(reinterpret_cast<const char*>(password.data()), password.size(),
                       envelope.data() + WALLET_FORMAT.size(), SALT_SIZE, 1 << 17, 8, 1,
                       uint64_t{256} * 1024 * 1024, key.data(), key.size()) != 1) {
        throw std::runtime_error("Falha ao derivar a chave de cifragem.");
    }
    return key;
}

void DecryptWallet(std::span<unsigned char> public_key, std::span<unsigned char> secret)
{
    const auto password = ReadPassword();
    Envelope envelope{};
    ReadExact(envelope);
    if (!std::ranges::equal(WALLET_FORMAT, std::span{envelope}.first(WALLET_FORMAT.size()))) {
        throw std::runtime_error("Formato de carteira inválido.");
    }
    const auto key = DeriveKey(password, envelope);
    CipherContext ctx{EVP_CIPHER_CTX_new(), EVP_CIPHER_CTX_free};
    SecureBytes plaintext(BODY_SIZE + EVP_MAX_BLOCK_LENGTH);
    int output{0}, final_output{0};
    if (!ctx || EVP_DecryptInit_ex(ctx.get(), EVP_aes_256_gcm(), nullptr, key.data(),
                                  envelope.data() + WALLET_FORMAT.size() + SALT_SIZE) != 1 ||
        EVP_DecryptUpdate(ctx.get(), nullptr, &output, envelope.data(), WALLET_FORMAT.size()) != 1 ||
        EVP_DecryptUpdate(ctx.get(), plaintext.data(), &output, envelope.data() + HEADER_SIZE, BODY_SIZE) != 1 ||
        EVP_CIPHER_CTX_ctrl(ctx.get(), EVP_CTRL_GCM_SET_TAG, TAG_SIZE, envelope.data() + HEADER_SIZE + BODY_SIZE) != 1 ||
        EVP_DecryptFinal_ex(ctx.get(), plaintext.data() + output, &final_output) != 1 ||
        static_cast<size_t>(output + final_output) != BODY_SIZE) {
        throw std::runtime_error("Senha incorreta ou arquivo de carteira adulterado.");
    }
    std::ranges::copy(std::span{plaintext}.first(public_key.size()), public_key.begin());
    std::ranges::copy(std::span{plaintext}.subspan(public_key.size(), secret.size()), secret.begin());
}

Envelope EncryptWallet(const SecureBytes& password, const SecureBytes& keys)
{
    Envelope envelope{};
    std::ranges::copy(WALLET_FORMAT, envelope.begin());
    if (RAND_bytes(envelope.data() + WALLET_FORMAT.size(), SALT_SIZE + NONCE_SIZE) != 1) {
        throw std::runtime_error("Não foi possível gerar o sal e o nonce da carteira.");
    }
    const auto key = DeriveKey(password, envelope);
    CipherContext ctx{EVP_CIPHER_CTX_new(), EVP_CIPHER_CTX_free};
    std::array<unsigned char, BODY_SIZE + EVP_MAX_BLOCK_LENGTH> ciphertext{};
    int output{0}, final_output{0};
    if (!ctx || EVP_EncryptInit_ex(ctx.get(), EVP_aes_256_gcm(), nullptr, key.data(),
                                  envelope.data() + WALLET_FORMAT.size() + SALT_SIZE) != 1 ||
        EVP_EncryptUpdate(ctx.get(), nullptr, &output, envelope.data(), WALLET_FORMAT.size()) != 1 ||
        EVP_EncryptUpdate(ctx.get(), ciphertext.data(), &output, keys.data(), keys.size()) != 1 ||
        EVP_EncryptFinal_ex(ctx.get(), ciphertext.data() + output, &final_output) != 1 ||
        static_cast<size_t>(output + final_output) != BODY_SIZE ||
        EVP_CIPHER_CTX_ctrl(ctx.get(), EVP_CTRL_GCM_GET_TAG, TAG_SIZE, envelope.data() + HEADER_SIZE + BODY_SIZE) != 1) {
        throw std::runtime_error("Não foi possível cifrar a carteira.");
    }
    std::copy_n(ciphertext.begin(), BODY_SIZE, envelope.begin() + HEADER_SIZE);
    return envelope;
}

void WriteResult(std::span<const unsigned char> bytes)
{
    if (std::fwrite(bytes.data(), 1, bytes.size(), stdout) != bytes.size() || std::fflush(stdout) != 0) {
        throw std::runtime_error("Não foi possível gravar o resultado.");
    }
}
} // namespace

int Real26CreateWallet(bool from_seed, int (*keygen)(const char*, uint8_t*, uint8_t*))
{
    try {
        const auto password = ReadPassword();
        SecureBytes keys(BODY_SIZE);
        if (!keygen(from_seed ? "derivar-v1" : "gerar", keys.data(), keys.data() + PUBLIC_SIZE)) {
            throw std::runtime_error("Não foi possível gerar as chaves ML-DSA-65.");
        }
        const Envelope envelope = EncryptWallet(password, keys);
        // O processo pai recebe somente a chave pública e o arquivo cifrado.
        WriteResult(std::span{keys}.first(PUBLIC_SIZE));
        WriteResult(envelope);
        return EXIT_SUCCESS;
    } catch (const std::exception& error) {
        std::fprintf(stderr, "Carteira ML-DSA-65: %s\n", error.what());
        return EXIT_FAILURE;
    }
}

int Real26SignTransaction(std::string_view command)
{
    // O assinador recebe dados pelo canal local do processo, sem RPC de chave.
    std::vector<unsigned char> public_key(OQS_SIG_ml_dsa_65_length_public_key);
    SecureBytes secret(OQS_SIG_ml_dsa_65_length_secret_key);
    try {
        if (command != "assinar-carteira" && command != "abrir-publica") {
            ReadExact(public_key);
            ReadExact(secret);
        } else {
            DecryptWallet(public_key, secret);
        }
        if (command == "abrir-publica") {
            if (std::fgetc(stdin) != EOF || std::ferror(stdin)) throw std::runtime_error("Dados excedentes.");
            WriteResult(public_key);
            return EXIT_SUCCESS;
        }

        std::vector<unsigned char> bytes(MAX_STANDARD_TX_WEIGHT + 1);
        const size_t count = std::fread(bytes.data(), 1, bytes.size(), stdin);
        if (count == bytes.size() || std::ferror(stdin)) throw std::runtime_error("Entrada excede o limite local.");
        SpanReader stream{std::span<const unsigned char>{bytes.data(), count}};
        CMutableTransaction tx;
        std::vector<CTxOut> prevouts;
        stream >> TX_NO_WITNESS(tx) >> prevouts;
        if (stream.size() != 0 || tx.vin.empty() || tx.vout.empty() || prevouts.size() != tx.vin.size()) {
            throw std::runtime_error("Transação ou saídas anteriores inválidas.");
        }

        // A testemunha tem dois itens, cada um com tamanho CompactSize de 3 bytes.
        constexpr size_t witness_weight{1 + 3 + OQS_SIG_ml_dsa_65_length_signature +
                                        3 + OQS_SIG_ml_dsa_65_length_public_key};
        if (GetSerializeSize(TX_NO_WITNESS(tx)) * 4 + 2 + tx.vin.size() * witness_weight > MAX_STANDARD_TX_WEIGHT) {
            throw std::runtime_error("O gasto ML-DSA-65 excede o peso padrão de uma transação.");
        }

        HashWriter hasher;
        hasher.write(std::as_bytes(std::span{public_key}));
        const uint256 commitment = hasher.GetSHA256();
        const CScript expected{CScript() << OP_2 << std::span{commitment.begin(), commitment.end()}};
        std::set<COutPoint> used;
        for (size_t i = 0; i < tx.vin.size(); ++i) {
            if (!tx.vin[i].scriptSig.empty() || tx.vin[i].prevout.IsNull() ||
                !used.insert(tx.vin[i].prevout).second ||
                prevouts[i].scriptPubKey != expected || !MoneyRange(prevouts[i].nValue)) {
                throw std::runtime_error("Entrada inválida ou pertencente a outra carteira.");
            }
        }
        PrecomputedTransactionData precomputed;
        precomputed.Init(tx, std::move(prevouts), /*force=*/true);
        const auto& genesis = command == "assinar-tx-testnet-refs" ? REAL26_TEST_REFS_GENESIS
            : command == "assinar-tx-refs" ? REAL26_REFS_GENESIS : REAL26_DEV_GENESIS;
        for (unsigned int i = 0; i < tx.vin.size(); ++i) {
            if (!SignReal26Mldsa65Input(tx, i, precomputed, public_key, secret, genesis)) {
                throw std::runtime_error("Não foi possível assinar com o par de chaves ML-DSA-65.");
            }
        }
        DataStream result;
        result << TX_WITH_WITNESS(tx);
        WriteResult({UCharCast(result.data()), result.size()});
        return EXIT_SUCCESS;
    } catch (const std::exception& error) {
        std::fprintf(stderr, "Assinatura ML-DSA-65: %s\n", error.what());
        return EXIT_FAILURE;
    }
}
