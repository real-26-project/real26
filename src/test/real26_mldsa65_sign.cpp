// Distribuído sob a licença MIT. Consulte o arquivo COPYING.
#include <oqs/oqs.h>
#include <oqs/rand.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <string_view>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

int Real26SignTransaction(std::string_view command);
int Real26CreateWallet(bool from_seed, int (*keygen)(const char*, uint8_t*, uint8_t*));

// A derivação experimental fornece a entropia de 32 bytes de KeyGen do FIPS 204.
static uint8_t entropia[32];
static int entropia_usada;

static void fornecer_entropia(uint8_t *destino, size_t tamanho)
{
    // A implementação fixada solicita exatamente 32 bytes, uma única vez.
    if (entropia_usada || tamanho != sizeof(entropia)) abort();
    memcpy(destino, entropia, tamanho);
    entropia_usada = 1;
}

static int gerar_chaves(const char *comando, uint8_t *publica, uint8_t *privada)
{
    if (strcmp(comando, "gerar") == 0) {
        return OQS_SIG_ml_dsa_65_keypair(publica, privada) == OQS_SUCCESS;
    }
    if (fread(entropia, 1, sizeof(entropia), stdin) != sizeof(entropia) || fgetc(stdin) != EOF || ferror(stdin)) {
        OQS_MEM_cleanse(entropia, sizeof(entropia));
        return 0;
    }
    // O gerador determinístico existe só neste processo de geração de chaves.
    OQS_randombytes_custom_algorithm(fornecer_entropia);
    const int resultado = OQS_SIG_ml_dsa_65_keypair(publica, privada);
    OQS_MEM_cleanse(entropia, sizeof(entropia));
    return resultado == 0 && entropia_usada;
}

int main(int argc, char **argv)
{
    if (argc != 2) return EXIT_FAILURE;
#ifdef _WIN32
    if (_setmode(_fileno(stdin), _O_BINARY) == -1 || _setmode(_fileno(stdout), _O_BINARY) == -1) return EXIT_FAILURE;
#endif
    uint8_t publica[OQS_SIG_ml_dsa_65_length_public_key];
    uint8_t privada[OQS_SIG_ml_dsa_65_length_secret_key] = {0};
    int resultado = EXIT_FAILURE;
    OQS_init();
    if (strcmp(argv[1], "criar-carteira") == 0 || strcmp(argv[1], "restaurar-carteira-v1") == 0) {
        resultado = Real26CreateWallet(strcmp(argv[1], "restaurar-carteira-v1") == 0, gerar_chaves);
        OQS_destroy();
        return resultado;
    }
    if (strcmp(argv[1], "assinar-tx") == 0 || strcmp(argv[1], "assinar-tx-refs") == 0 ||
        strcmp(argv[1], "assinar-tx-testnet-refs") == 0 || strcmp(argv[1], "assinar-carteira") == 0 ||
        strcmp(argv[1], "abrir-publica") == 0) {
        resultado = Real26SignTransaction(argv[1]);
        OQS_destroy();
        return resultado;
    }
    // As chaves do teste passam por pipes, sem arquivos de chaves persistentes.
    if ((strcmp(argv[1], "gerar") == 0 || strcmp(argv[1], "derivar-v1") == 0) &&
        gerar_chaves(argv[1], publica, privada) &&
        fwrite(publica, 1, sizeof(publica), stdout) == sizeof(publica) &&
        fwrite(privada, 1, sizeof(privada), stdout) == sizeof(privada)) {
        resultado = EXIT_SUCCESS;
    }
    OQS_MEM_cleanse(privada, sizeof(privada));
    OQS_destroy();
    return resultado;
}
