# Código da REAL-26

A REAL-26 deriva do Bitcoin Core 32.1 e distribui o nó `real26d` e o cliente de linha de comando `real26-cli`. Os parâmetros, as regras de gasto e a carteira desktop da REAL-26 estão nos pontos abaixo.

| Componente | Onde consultar |
| --- | --- |
| Gênese, rede e parâmetros de consenso | [Parâmetros da cadeia](../../src/kernel/chainparams.cpp) e [argumentos da REAL-26](../../src/chainparamsbase.cpp) |
| Prova de trabalho e ajuste ASERT | [src/pow.cpp](../../src/pow.cpp) |
| Saídas ML-DSA-65 e regras de gasto | [src/script/real26_mldsa65.h](../../src/script/real26_mldsa65.h), [interpretador](../../src/script/interpreter.cpp) e [validação](../../src/validation.cpp) |
| Assinatura e operações da carteira | [Assinatura ML-DSA-65](../../src/wallet/real26_mldsa65_sign.cpp) e [RPCs da REAL-26](../../src/wallet/rpc/real26.cpp) |
| Aplicativo Windows e acesso ao nó | [Interface](../../carteira-desktop/carteira.py) e [integração RPC](../../carteira-desktop/no_real26.py) |
| Fluxos de abertura, pagamentos e backup | [Fluxos da carteira](../../carteira-desktop/fluxos_carteira.py) e [diálogos](../../carteira-desktop/dialogos.py) |
| Mineração integrada | [carteira-desktop/mineracao.py](../../carteira-desktop/mineracao.py) |
| Testes funcionais | [suíte da candidata](../../experimentos/verificar-candidata.sh) e [teste ASERT/ML-DSA-65](../../test/functional/feature_real26_asert_pq.py) |

Veja também as [instruções de instalação e compilação](../../INSTALL.md) e a [documentação técnica](../../README.pt-BR.md).
