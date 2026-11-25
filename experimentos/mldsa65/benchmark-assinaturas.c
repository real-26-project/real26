// Distribuído sob a licença MIT. Consulte COPYING.
#define _POSIX_C_SOURCE 200809L
#include <oqs/oqs.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

enum { AMOSTRAS = 7, OPERACOES = 1000, TAM_RESUMO = 32 };

static double agora(void)
{
    struct timespec hora;
    if (clock_gettime(CLOCK_MONOTONIC, &hora) != 0) exit(EXIT_FAILURE);
    return (double)hora.tv_sec + hora.tv_nsec / 1e9;
}

static int comparar(const void *a, const void *b)
{
    const double x = *(const double *)a;
    const double y = *(const double *)b;
    return (x > y) - (x < y);
}

static void preencher_resumo(uint8_t resumo[TAM_RESUMO], unsigned indice)
{
    for (unsigned i = 0; i < 4; ++i) resumo[i] = (uint8_t)(indice >> (8 * i));
}

int main(int argc, char **argv)
{
    if (argc != 2) return EXIT_FAILURE;
    OQS_init();
    OQS_SIG *algoritmo = OQS_SIG_new(argv[1]);
    if (!algoritmo) {
        fprintf(stderr, "Algoritmo indisponível: %s\n", argv[1]);
        OQS_destroy();
        return EXIT_FAILURE;
    }

    uint8_t *publica = malloc(algoritmo->length_public_key);
    uint8_t *privada = malloc(algoritmo->length_secret_key);
    uint8_t *assinaturas = malloc(OPERACOES * algoritmo->length_signature);
    size_t tamanhos[OPERACOES];
    double assinar[AMOSTRAS], verificar[AMOSTRAS];
    uint8_t resumo[TAM_RESUMO] = {0};
    int resultado = EXIT_FAILURE;
    if (!publica || !privada || !assinaturas ||
        OQS_SIG_keypair(algoritmo, publica, privada) != OQS_SUCCESS) goto fim;

    // A primeira rodada aquece a biblioteca e fica fora da medição.
    for (unsigned rodada = 0; rodada <= AMOSTRAS; ++rodada) {
        double inicio = agora();
        for (unsigned i = 0; i < OPERACOES; ++i) {
            preencher_resumo(resumo, rodada * OPERACOES + i);
            if (OQS_SIG_sign(algoritmo, assinaturas + i * algoritmo->length_signature,
                             &tamanhos[i], resumo, sizeof(resumo), privada) != OQS_SUCCESS) goto fim;
        }
        double assinado = agora();
        for (unsigned i = 0; i < OPERACOES; ++i) {
            preencher_resumo(resumo, rodada * OPERACOES + i);
            if (OQS_SIG_verify(algoritmo, resumo, sizeof(resumo), assinaturas + i * algoritmo->length_signature,
                               tamanhos[i], publica) != OQS_SUCCESS) goto fim;
        }
        if (rodada != 0) {
            assinar[rodada - 1] = 1e6 * (assinado - inicio) / OPERACOES;
            verificar[rodada - 1] = 1e6 * (agora() - assinado) / OPERACOES;
        }
    }
    qsort(assinar, AMOSTRAS, sizeof(double), comparar);
    qsort(verificar, AMOSTRAS, sizeof(double), comparar);
    printf("%s | chave pública %zu B | assinatura %zu B\n",
           algoritmo->method_name, algoritmo->length_public_key, algoritmo->length_signature);
    printf("Mediana de %d lotes de %d operações: assinar %.2f us, verificar %.2f us.\n",
           AMOSTRAS, OPERACOES, assinar[AMOSTRAS / 2], verificar[AMOSTRAS / 2]);
    resultado = EXIT_SUCCESS;

fim:
    if (resultado != EXIT_SUCCESS) fputs("Falha durante a medição criptográfica.\n", stderr);
    OQS_MEM_secure_free(privada, algoritmo->length_secret_key);
    free(publica);
    free(assinaturas);
    OQS_SIG_free(algoritmo);
    OQS_destroy();
    return resultado;
}
