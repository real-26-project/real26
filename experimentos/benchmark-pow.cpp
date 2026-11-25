// Distribuído sob a licença MIT. Consulte COPYING.
#include <crypto/sha256.h>

#include <algorithm>
#include <array>
#include <bit>
#include <charconv>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <string_view>
#include <thread>
#include <vector>

using Cabecalho = std::array<unsigned char, 80>;
using Relogio = std::chrono::steady_clock;

struct Amostra {
    uint64_t hashes{0};
    uint64_t soma{0};
};

Amostra medir(Cabecalho cabecalho, uint32_t nonce, uint32_t passo, Relogio::time_point fim)
{
    Amostra amostra;
    std::array<unsigned char, 32> intermediario;
    std::array<unsigned char, 32> hash;
    while (Relogio::now() < fim) {
        for (int i = 0; i < 4096; ++i) {
            for (unsigned int byte = 0; byte < 4; ++byte) {
                cabecalho[76 + byte] = static_cast<unsigned char>(nonce >> (8 * byte));
            }
            CSHA256().Write(cabecalho.data(), cabecalho.size()).Finalize(intermediario.data());
            CSHA256().Write(intermediario.data(), intermediario.size()).Finalize(hash.data());
            amostra.soma += hash.front();
            nonce += passo;
        }
        amostra.hashes += 4096;
    }
    return amostra;
}

int main(int argc, char** argv)
{
    if ((argc != 2 && argc != 3) || std::string_view{argv[1]}.size() != 160) {
        std::cerr << "Informe um cabeçalho de 80 bytes em hexadecimal e, opcionalmente, a quantidade de threads.\n";
        return 2;
    }

    Cabecalho cabecalho;
    const char* hex = argv[1];
    for (auto& byte : cabecalho) {
        unsigned int valor;
        const auto leitura = std::from_chars(hex, hex + 2, valor, 16);
        if (leitura.ec != std::errc{} || leitura.ptr != hex + 2) return 2;
        byte = static_cast<unsigned char>(valor);
        hex += 2;
    }

    std::cout << "SHA-256: " << SHA256AutoDetect() << std::endl;
    const unsigned int disponiveis = std::max(1U, std::thread::hardware_concurrency());
    const unsigned int concorrencia = std::bit_ceil(disponiveis);
    std::vector<unsigned int> configuracoes{1U, std::min(4U, disponiveis), disponiveis};
    if (argc == 3) {
        const std::string_view argumento{argv[2]};
        unsigned int threads{0};
        const auto leitura = std::from_chars(argumento.data(), argumento.data() + argumento.size(), threads);
        if (leitura.ec != std::errc{} || leitura.ptr != argumento.data() + argumento.size() ||
            threads == 0 || threads > disponiveis) {
            std::cerr << "Quantidade de threads fora do intervalo disponível.\n";
            return 2;
        }
        configuracoes = {threads};
    }
    uint64_t soma = 0;
    for (unsigned int threads : configuracoes) {
        std::array<double, 3> taxas;
        for (auto& taxa : taxas) {
            std::vector<Amostra> amostras(threads);
            std::vector<std::thread> mineradores;
            const auto inicio = Relogio::now();
            const auto fim = inicio + std::chrono::seconds{4};
            for (unsigned int i = 0; i < threads; ++i) {
                mineradores.emplace_back([&, i] { amostras[i] = medir(cabecalho, i, concorrencia, fim); });
            }
            for (auto& minerador : mineradores) minerador.join();
            const double duracao = std::chrono::duration<double>(Relogio::now() - inicio).count();
            uint64_t hashes = 0;
            for (const auto& amostra : amostras) {
                hashes += amostra.hashes;
                soma += amostra.soma;
            }
            taxa = hashes / duracao / 1'000'000;
        }
        std::ranges::sort(taxas);
        std::cout << threads << " threads: " << taxas[0] << ", " << taxas[1] << ", " << taxas[2]
                  << " MH/s (min, mediana, max)" << std::endl;
    }
    std::cout << "Soma de controle: " << soma << '\n';
}
