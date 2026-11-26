# REAL-26

Para instalar a carteira e participar da testnet, consulte o [guia de uso da REAL-26](doc/real26/uso.md).

A REAL-26 é um projeto brasileiro de moeda digital de código aberto. O objetivo é permitir que qualquer pessoa verifique as regras da moeda, rode seu próprio nó e mantenha a custódia das próprias chaves. A documentação do projeto é escrita em português brasileiro.

## Regras de gasto da rede de desenvolvimento

Desde o primeiro bloco, cada entrada que movimenta moedas precisa gastar uma saída nativa SegWit v2 com compromisso SHA-256 de 32 bytes. O nó exige uma chave pública ML-DSA-65 correspondente ao compromisso, uma assinatura válida para aquela entrada e um scriptSig vazio. P2PKH, P2SH, SegWit v0, Taproot e outras versões de testemunha são incompatíveis com esse consenso.

A mempool e os blocos rejeitam saídas fora desse formato, inclusive no pagamento da recompensa de mineração. Saídas OP_RETURN são permitidas para dados e compromissos de testemunha. Elas são irrecuperáveis. Para minerar e receber a recompensa, use um endereço de `getreal26address` ou da carteira externa ML-DSA-65.

A alteração inicia uma cadeia de desenvolvimento nova a partir do mesmo gênese. O diretório e o identificador P2P anteriores pertencem ao protótipo incompatível. As chaves e os arquivos de backup continuam úteis para restaurar os endereços em uma carteira nova. Os saldos da cadeia anterior não são transferidos.

## Versão candidata para revisão

A meta interna é fechar até **30 de novembro de 2026** uma versão candidata executável por linha de comando, com código, dependências e procedimento de verificação documentados. A auditoria externa ocorre após o fechamento da candidata.

| Data-alvo | Entrega |
|---|---|
| 23 de novembro | Fechar a especificação da rede de produção, incluindo emissão, recompensa, ajuste de dificuldade e parâmetros do gênese e da rede. |
| 26 de novembro | Validar uma compilação limpa e ensaiar, em rede privada, sincronização, reinício e recuperação de carteira com os parâmetros candidatos. |
| 30 de novembro | Fechar a revisão interna e preparar o código, as instruções de compilação e os resultados para auditoria. |

A testnet com referências usa ML-DSA-65, 4 milhões de unidades de peso e alvo de cinco minutos. Sua prova de trabalho foi dimensionada para experimentos em CPU. Os parâmetros da rede de produção ainda precisam ser definidos. Os marcos acima são metas de preparação para auditoria.

Para verificar a compilação de desenvolvimento atual no WSL:

```bash
bash experimentos/verificar-candidata.sh build
```

O comando verifica as opções de compilação e executa as oito suítes funcionais da REAL-26, incluindo os laboratórios ASERT e a testnet compartilhada. Após todas passarem, grava `build/real26-candidata.csv` com o resultado e a duração de cada suíte.

Para a candidata, registre a revisão do Core e da liboqs, a configuração de compilação, os hashes dos binários e o resultado das suítes a partir de uma árvore limpa. A revisão de segurança acompanha os avisos do [Bitcoin Core](https://bitcoincore.org/en/security-advisories/) e da [liboqs](https://github.com/open-quantum-safe/liboqs/security/advisories). Consulte a [política de segurança](SECURITY.md) para relatar uma falha.

### Proposta de parâmetros de produção

| Parâmetro | Proposta para a candidata |
|---|---|
| Intervalo-alvo | 300 segundos |
| Peso máximo de bloco | 4.000.000 unidades |
| Autorização de gastos | ML-DSA-65, com a codificação canônica avaliada na testnet isolada |
| Prova de trabalho | SHA-256 duplo |
| Subsídio inicial | 25 REAL-26 por bloco, a partir da altura 1 |
| Redução do subsídio | A cada 420.000 blocos, aproximadamente quatro anos no intervalo-alvo |
| Gênese | Saída de valor zero com a declaração proposta abaixo |
| Ajuste de dificuldade para ensaio privado | A cada 144 blocos, com variação do alvo limitada a um quarto ou quatro vezes o valor anterior por ajuste |
| Rede e assinaturas | Gênese e domínio de assinatura próprios, identificador P2P e prefixo de endereços exclusivos |

Com blocos numerados desde zero, subsídio de gênese zero e reduções por divisão inteira, a emissão máxima teórica é **20.999.974,95380000 REAL-26**. A primeira redução cai na altura 420.000, a partir da qual o subsídio é 12,5. O subsídio zera na altura 13.440.000. As taxas transferem moedas já existentes. Esses valores propõem uma curva de emissão próxima de 21 milhões, com reduções aproximadamente quadrienais. O subsídio de 25 está ativo na rede privada de ensaio. A proposta de produção ainda depende da configuração final da rede.

Com média de cinco minutos, são cerca de 7.200 REAL-26 novos por dia no primeiro período. Por volta de 4 anos, terão sido emitidos 50% do máximo. Por volta de 16 anos, 93,75%. Por volta de 28 anos, 99,22%. O subsídio só zera perto de 128 anos, nessa média. As reduções seguem a altura do bloco. Uma sequência de blocos rápidos adianta o calendário de emissão até que o reajuste assimile a taxa de mineração.

O ensaio matemático compara períodos de ajuste de 144 e 2.016 blocos. Para uma perda abrupta de 90% do poder de mineração logo no começo do período, com 144 blocos o primeiro ajuste demoraria cerca de 5 dias no modelo e o seguinte, 30 horas. Com 2.016 blocos, seriam cerca de 70 dias e 17,5 dias. Um aumento abrupto de dez vezes produz, com 144 blocos, dois períodos de cerca de 1,2 e 4,8 horas até o intervalo voltar à faixa de 5 minutos. O modelo usa intervalos médios fixos, ignora a aleatoriedade da mineração e a compactação e pressupõe que os limites absolutos de dificuldade não interrompam os ajustes.

```bash
python3 experimentos/parametros_producao.py
```

A dificuldade inicial e o limite máximo do alvo de produção ficam pendentes até medirmos o poder de mineração disponível e sua distribuição entre os participantes. A próxima validação deve usar os mineradores candidatos numa rede privada, medir a taxa de hashes e retirar parte dela durante o ensaio. A mensagem final do gênese fica para aprovação antes de fixar seu hash e o domínio de assinatura.

Para o ensaio de lançamento, compare uma janela de 144 blocos com a de 2.016, usando a mesma taxa inicial e cenários de entrada e saída de mineradores. Uma janela de 144 blocos leva nominalmente 12 horas e a de 2.016 leva 7 dias. Em um modelo com aumento de duas vezes logo no começo da janela, a primeira janela cai para cerca de 6 horas ou 3,5 dias, respectivamente. Isso significa 3.600 REAL-26 de subsídio por janela de 144 blocos e 50.400 por janela de 2.016, desconsiderado o desconto de 25 no gênese. A janela menor acelera a reação a mudanças e precisa ser validada com horários de bloco variáveis e mineradores independentes.

### Estratégia de mineração para a rede pública

#### Comparação do reajuste por janela com ASERT

```bash
python3 experimentos/parametros_producao.py --comparar-dificuldade 500
```

O modelo usa uma espera exponencial entre blocos, o mesmo alvo inicial calibrado para 5 minutos e 500 sementes por regra e cenário. A mudança de potência começa na fronteira de uma janela. A recuperação começa quando 24 blocos consecutivos têm intervalo esperado entre 4,5 e 5,5 minutos. A tabela mostra a mediana. A emissão do primeiro dia é medida em relação às 7.200 REAL-26 previstas.

| Mudança na potência | 144 blocos, emissão em 24 h / recuperação | ASERT de 3 h, emissão em 24 h / recuperação |
|---|---:|---:|
| Dobrou | +1.700 / 6,2 h | +875 / 7,9 h |
| Multiplicou por dez | +5.300 / 6,1 h | +2.975 / 10,4 h |
| Caiu pela metade | −3.575 / 24,8 h | −900 / 11,3 h |
| Caiu 90% | −6.475 / 149,7 h | −2.975 / 20,5 h |

Com potência multiplicada por dez, a janela de 2.016 blocos adiantou 48.550 REAL-26 no primeiro dia. Entre as meias-vidas simuladas de 3, 6, 12 e 48 horas, a de 3 horas teve a menor emissão extra nos dois aumentos de potência. Ela também reage mais a desvios de horário. Uma hora adiantada eleva o alvo instantâneo em cerca de 26% nesse modelo. Por isso, a candidata para um ensaio separado é ASERT com meia-vida de 3 horas, incluindo testes de limites de timestamp, alvo máximo, reorganização, interrupções e compatibilidade entre nós. [Especificação do ASERT](https://upgradespecs.bitcoincashnode.org/2020-11-15-asert/)

A simulação usa aritmética aproximada, sem compactação do alvo, sem limite máximo de alvo e sem validação de timestamps. O cenário de horário desloca todos os blocos posteriores em uma hora. A rede atual continua com o reajuste de 144 blocos. A escolha para produção depende do ensaio de consenso e da potência medida.

#### Laboratório de consenso ASERT

O modo `-regtest -real26asert` usa gênese, identificador P2P, diretório de dados e portas próprios. A âncora é o gênese, a meta é de 300 segundos e a meia-vida é de 10.800 segundos. O cálculo é feito com inteiros, arredondado para `nBits` e limitado ao alvo máximo do laboratório. Esse perfil usa as regras de transação do regtest para exercitar a prova de trabalho.

```bash
cmake --build build --target bitcoind bitcoin-cli -j 7
python3 test/functional/feature_real26_asert.py --configfile=build/test/config.ini --usecli
```

Em dois nós conectados por P2P, o teste confere o próximo `nBits` contra uma referência em Python. Os nós mineram e sincronizam blocos de ensaio com horários controlados. O teste verifica o endurecimento com blocos rápidos, a queda de dificuldade após um atraso de três horas em relação ao calendário, o limite do alvo, a rejeição de um bloco com alvo incorreto e os limites de horário do cabeçalho. [Especificação do ASERT](https://upgradespecs.bitcoincashnode.org/2020-11-15-asert/)

Com `-regtest -real26asert -real26dev`, o laboratório usa ML-DSA-65 com referências canônicas, endereços `r26ap`, gênese e domínio de assinatura próprios e subsídio inicial de 25 REAL-26. O teste abaixo conecta três processos locais por P2P. Dois mineradores produzem 127 blocos, um sai e volta, e o terceiro nó confirma um pagamento de duas entradas. Os horários são controlados para exercitar a resposta a mudanças de ritmo. O teste acelera a retransmissão entre pares locais e verifica a aceitação do pagamento. Para avaliar a regra para produção, ainda faltam testes longos com operadores em máquinas e conexões diferentes e avaliação de desvios de horário dentro dos limites aceitos.

```bash
python3 test/functional/feature_real26_asert_pq.py --configfile=build/test/config.ini --usecli
```

#### Testnet compartilhada com ASERT

O perfil `-testnet4 -real26test -real26testrefs -real26testasert` adota ASERT com meta de 5 minutos e meia-vida de 3 horas. Ele usa endereços `r26s`, porta P2P 29838, RPC 29837, diretório `real26testasert-v2`, gênese e domínio de assinatura próprios. O alvo inicial de teste é `0x1c10e331`. O teste isolado tem cadeia e saldos próprios.

Operadores precisam combinar um endereço P2P alcançável para o primeiro nó. Os demais podem adicionar esse endereço com `-addnode=HOST:29838`. Use o RPC apenas em loopback, autenticado pelo cookie do nó. O protocolo aceita conexões entre nós da mesma testnet. As moedas desta rede são de ensaio e não têm valor monetário.

Na carteira nativa, clique em **Conectar à testnet**. O perfil compartilhado fica em `%LOCALAPPDATA%\REAL-26\No-testnet-ASERT-v2`. O ASERT usa o primeiro bloco minerado como referência, com meta de 5 minutos e meia-vida de 3 horas. O alvo inicial `0x1c10e331` exige cerca de 65 bilhões de hashes em média, calibrado para a Radeon do ensaio. Só com CPU o intervalo inicial esperado é maior. A versão anterior mantém seus dados no diretório No-testnet-ASERT. A carteira tenta o nó inicial da AWS em `carteira-desktop/pares-testnet.txt` via IPv4 e passa a descobrir outros pares após conectar. O endereço público da instância de teste pode mudar se ela for parada e iniciada novamente. O IP da conexão fica visível para os pares.

Para cadastrar outro par, use **Adicionar nó**. Informe um endereço no formato `host:29838`. Para IPv6, use `[IPv6]:29838`. A carteira guarda os endereços adicionais para as próximas sessões. No terminal, use `--testnet`; a opção `--par` pode ser repetida para acrescentar endereços.

Quando a rede compartilhada contém apenas a gênese, conecte a carteira a pelo menos um par. Se o nó ainda não conhece cabeçalhos posteriores à gênese, a carteira mostra **Aguardando primeiro bloco** e permite iniciar a mineração. Se o nó detectar blocos mais novos, a mineração aguarda a sincronização.

### Prévia pública da testnet

O instalador desta fase distribui uma carteira de ensaio. As moedas de teste não têm valor e a cadeia pode ser reiniciada. Os perfis compartilhado e isolado mantêm carteiras e saldos separados.

Antes de divulgar a prévia, valide o acesso P2P na porta 29838 de nós em redes independentes e preencha a lista de pares do instalador com os endereços verificados. A carteira usa RPC local. Em duas instalações externas, confira a gênese e o hash do topo após sincronizar. Envie um pagamento de teste entre as instalações e confirme que ambas reconhecem sua inclusão no mesmo bloco.

Registre a versão do aplicativo, o horário, o tempo de sincronização, a quantidade de pares, os intervalos entre blocos e o tempo até a confirmação do pagamento. Para relatar falhas, descreva os passos e inclua somente logs revisados. Nunca envie senhas, chaves, backups ou cookies RPC. Use o canal privado indicado em `SECURITY.md` para vulnerabilidades.

```bash
python3 test/functional/feature_real26_asert_pq.py --configfile=build/test/config.ini --compartilhado --usecli
```

#### Regra por janela em avaliação

A proposta usa prova de trabalho SHA-256 duplo, mineração aberta, seleção pela maior quantidade de trabalho acumulado e o reajuste periódico do Bitcoin. Para manter o alvo de 5 minutos com os 2.016 blocos por janela do Bitcoin, o período nominal da REAL-26 seria de 7 dias. O reajuste usa os horários dos blocos da janela, limita a variação do alvo a um quarto ou quatro vezes o valor anterior e respeita o alvo máximo permitido. A versão privada usa 144 blocos para testar a regra num ciclo curto.

O nó fornece o modelo de bloco via `getblocktemplate` e recebe soluções via `submitblock`. A compatibilidade operacional com ASICs precisa ser demonstrada com um servidor de mineração compatível e equipamento real. O protocolo aceita provas válidas vindas de qualquer tipo de equipamento. A participação efetiva depende da taxa de hashes de cada operador.

O alvo inicial é um parâmetro da REAL-26. O alvo histórico do gênese do Bitcoin é uma referência para ensaios em CPU. Para uma janela de 2.016 blocos iniciada com um alvo calibrado e uma perda de metade da taxa de mineração logo no começo da janela, a projeção é de 10 minutos por bloco por cerca de 14 dias até o próximo ajuste. Esse risco precisa ser considerado antes de fixar o alvo e a janela da rede pública.

### Medição de mineração no alvo do gênese do Bitcoin

O processador Intel Xeon E5-2680 v4, com 28 processadores lógicos disponíveis no WSL, executou o SHA-256 duplo do Core sobre um cabeçalho de 80 bytes com a raiz de Merkle da REAL-26 e `nBits=0x1d00ffff`. Foram três amostras de quatro segundos por configuração. A medição conta cabeçalhos processados e usa a biblioteca de criptografia da compilação de desenvolvimento, com a implementação SSE4 para um cabeçalho por chamada.

| Threads | Taxa mediana | Intervalo médio projetado no alvo |
|---:|---:|---:|
| 1 | 1,189 MH/s | 60,21 min |
| 4 | 4,382 MH/s | 16,34 min |
| 28 | 14,538 MH/s | 4,92 min |

O alvo exige cerca de 4,295 bilhões de hashes por bloco em média. Para 5 minutos seriam necessários 14,317 MH/s sustentados. A medição com 28 threads ficou perto desse valor durante a amostragem. A previsão usa uma taxa fixa e representa trabalho médio. O ensaio mede o processamento local de cabeçalhos, sem medir tempo real entre blocos, disponibilidade contínua ou poder agregado dos mineradores de lançamento.

```bash
c++ -std=c++20 -O3 -pthread -Isrc experimentos/benchmark-pow.cpp build/lib/libbitcoin_crypto.a -o build/benchmark-pow
build/benchmark-pow 010000000000000000000000000000000000000000000000000000000000000000000000abcecc6de4bca46aee12c575f64f495d12a3526c39f32ad0baba1607e7d13ab5808dff6affff001d00000000
```

### Comparação local da Radeon com o Xeon

O benchmark executou SHA-256 duplo sobre o mesmo cabeçalho de 80 bytes. A Radeon RX 580 2048SP rodou OpenCL no Windows e o Xeon E5-2680 v4 rodou a biblioteca do Core no WSL. O código verificou os primeiros 32 bits de quatro hashes da GPU contra o SHA-256 duplo calculado na CPU. A primeira versão do kernel falhou nessa verificação com a otimização do driver. A versão medida usa desenrolamento explícito das rodadas e passou na verificação.

| Configuração | CPU | GPU | Soma das taxas |
|---|---:|---:|---:|
| CPU sozinha, 28 threads | 14,54 MH/s | — | 14,54 MH/s |
| GPU sozinha, duas séries | — | 256,06–257,41 MH/s | 256,06–257,41 MH/s |
| GPU e CPU, 4 threads | 4,27 MH/s | 249,84 MH/s | 254,11 MH/s |
| GPU e CPU, 28 threads | 14,24 MH/s | 100,89 MH/s | 115,12 MH/s |

A GPU sozinha foi a configuração mais rápida neste ensaio. As amostras isoladas duraram quatro segundos, três por série. A etapa combinada mediu a GPU durante o ensaio de CPU de aproximadamente 12 segundos. A soma representa o trabalho processado, sem coordenação de faixas de nonce ou distribuição de trabalho de mineração. A causa da queda da GPU com a CPU ocupada ainda precisa ser isolada.

A 256,06 MH/s, a projeção é de 16,8 segundos no alvo histórico `0x1d00ffff` e o alvo calculado para 5 minutos é `0x1c0e5020`. O benchmark mede cabeçalhos processados. A medição de blocos aceitos continuamente exige conectar o minerador ao nó privado.

No PowerShell, depois de compilar o benchmark de CPU no WSL:

```powershell
python experimentos/benchmark_pow_gpu.py --cpu-wsl /opt/real26/build/benchmark-pow --threads 4
```

### Blocos minerados pela Radeon e aceitos pelo nó

No PowerShell, o ensaio inicia um nó privado isolado no WSL, cria uma carteira temporária de mineração e monta candidatos a partir da ponta do nó. A Radeon busca o nonce e a CPU confere o hash completo antes de chamar `submitblock`. O cabeçalho carrega o alvo de consenso do ensaio (`0x1f0fffff`). O minerador aceita somente soluções que também satisfaçam o alvo histórico do gênese do Bitcoin (`0x1d00ffff`).

| Altura | Busca da solução | Taxa durante a busca | Hash aceito |
|---:|---:|---:|---|
| 1 | 46,868 s | 217,027 MH/s | `0000000094298c5a46a9fc1438b2d9fc5b059b94980caa85ccf566e40ef6521f` |
| 2 | 22,123 s | 214,163 MH/s | `0000000052d2d2c5fdb8f6dcdc70757d3196f1b1eb050dba75b0b210dba342a2` |
| 3 | 24,494 s | 217,400 MH/s | `0000000032591490b56d623113930bacfaf93aadc42a48e5638baa0d6cefee70` |

O nó aceitou os três blocos consecutivos, cada um com uma recompensa de 25 REAL-26 para a carteira do ensaio. Os blocos continham apenas a transação de recompensa. Os tempos cobrem a busca, e a amostra de três soluções tem variação de mineração. O nó de ensaio foi encerrado com os dados em `/tmp/real26-gpu.eMDr8guk` no WSL.

```powershell
$env:PYTHONPATH = 'test/functional'
python experimentos/mineracao_gpu.py
```

### Mineração pela Radeon com modelo RPC e pagamento

O ensaio com dois nós privados no WSL usou `getblocktemplate` para montar o bloco e conferiu o compromisso de testemunha fornecido pelo nó. A carteira enviou 37,5 REAL-26 de teste em uma transação de duas entradas, com a segunda chave codificada por referência. O nó receptor tinha a transação na mempool antes da mineração.

A Radeon encontrou a prova de trabalho em **25,192 s**, à taxa de **217,573 MH/s**, sob o mesmo filtro local `0x1d00ffff`. Após `submitblock`, o segundo nó aceitou o bloco em **0,657 s** e registrou uma confirmação na carteira de destino. O tempo inclui chamadas RPC locais. Foi uma amostra, em dois nós no mesmo computador.

- Bloco 103: `00000000987fafbdf6218c8deb193c0f5749f63781d53e9bec3130502a3f825c`
- Transação: `4287e1eb56c8531ee2603ef5be08841fdb2bb8f438c792c46cd023e2e56fbd31`

```powershell
$env:PYTHONPATH = 'test/functional'
python experimentos/mineracao_gpu.py --pagamento
```

### Ensaio de 30 minutos com mineração pela Radeon

Dois nós privados no WSL confirmaram sete pagamentos em sete blocos durante 1.800,62 segundos. A GPU manteve **216,083 MH/s** durante os 1.733,90 segundos de busca. O intervalo mediano entre blocos aceitos foi de **264,992 s**, calculado com seis intervalos. A mediana entre a submissão e a aceitação no segundo nó foi de **0,638 s**, em rede local.

Na metade do ensaio, o receptor reiniciou com os mesmos dados e retomou a conexão durante uma pausa de 15 segundos na mineração. Ele confirmou mais três blocos após a retomada. O minerador usou o filtro local `0x1c10e331` e os nós aplicaram o alvo de consenso da rede privada. A medição de meia hora avalia a integração e a recuperação. A amostra de sete blocos é pequena para calibrar o intervalo da rede.

```powershell
$env:PYTHONPATH = 'test/functional'
python experimentos/mineracao_gpu_continua.py --minutos 30
```

### Alvos iniciais por cenário de mineração

O cálculo usa o alvo inteiro derivado da taxa agregada de hashes, arredonda para a representação compacta do Core e calcula novamente a média esperada a partir desse valor. Os cenários de ASIC usam taxas nominais ilustrativas. A linha da CPU usa a mediana medida no WSL.

| Participação no início | Taxa agregada | `nBits` para média de 5 min |
|---|---:|---|
| CPU do ensaio | 14,54 MH/s | `0x1d00fc1b` |
| Um ASIC de 104 TH/s | 104 TH/s | `0x1a024f3d` |
| Um ASIC de 200 TH/s | 200 TH/s | `0x1a013372` |
| Dois ASICs de 104 TH/s | 208 TH/s | `0x1a01279e` |
| Três ASICs de 104 TH/s | 312 TH/s | `0x1a00c514` |

No cenário de três ASICs iguais, a saída de um no início de uma janela de 144 blocos leva a 7,5 minutos por bloco e cerca de 18 horas até o primeiro ajuste. Com dois ASICs iguais, a saída de um leva a 10 minutos por bloco e cerca de 24 horas. Essas projeções pressupõem taxa constante após a saída, ausência de nova perda e um limite de alvo que permita tornar a mineração mais fácil. Distribuir a taxa entre operadores diferentes reduz o impacto da saída de um único operador.

```bash
python3 experimentos/parametros_producao.py --hashrate 312000000000000
```

Nenhum desses cenários fixa o alvo de produção. A escolha depende da taxa sustentada confirmada e da participação por operador no início da rede.

### Mensagens propostas para o gênese

A frase curta vai no campo de entrada da coinbase.

> Brasil soberano, povo livre. Nossa voz, nosso trabalho e nosso futuro nos pertencem.

A declaração completa vai na saída de valor zero, como dados `OP_RETURN` no mesmo bloco.

> Queremos um Brasil soberano, onde ninguém tema falar, onde cada pessoa possa guardar o fruto do seu trabalho e onde todo poder responda ao povo. A liberdade é o direito de decidir o próprio futuro.

Em UTF-8, a frase curta tem 84 bytes e ocupa 93 bytes no `scriptSig` com a codificação atual. A declaração completa tem 200 bytes e ocuparia 209 bytes no `scriptSig`, acima do limite de 100. Na saída `OP_RETURN`, o script tem 203 bytes e conserva a declaração inteira. O ensaio serializa a coinbase e verifica a leitura exata das mensagens. O hash do bloco depende dos parâmetros finais do gênese.

```bash
PYTHONPATH=test/functional python3 experimentos/mensagem_genese.py
```

O mesmo comando monta um bloco de ensaio com versão 1, timestamp 1795132800 (20 de novembro de 2026, 00h UTC) e dificuldade da testnet. A coinbase aponta para a saída nula no índice `0xffffffff`. O ensaio confere a raiz de Merkle, a prova de trabalho e os bytes recuperados após desserializar o bloco.

| Campo | Valor de ensaio |
|---|---|
| Hash | `0007326bf77a1489a5e6ee7aa98affe5baac14aa7f2b694a86e2b54c8ae24733` |
| Raiz de Merkle | `b53ad1e70716babad02af3396c52a3125d494ff675c512ee6aa4bce46dccceab` |
| `nBits` | `0x1f0fffff` |
| Nonce | 3918 |

O bloco é um resultado reproduzível para o ensaio. O timestamp e a dificuldade de produção serão escolhidos para o lançamento antes de fixar o hash usado no domínio de assinatura.

### Rede privada de ensaio dos parâmetros candidatos

Inicie o nó e o cliente RPC com `-testnet4 -real26test -real26testrefs -real26ensaio`. Esta rede usa o gênese com os dois textos, endereços `r26e`, subdiretório `real26ensaio`, identificador P2P `b493d588`, porta P2P 29794 e RPC 29793.

O consenso tem 4 milhões de unidades de peso por bloco, alvo de 5 minutos, ajuste a cada 144 blocos e referências canônicas ML-DSA-65. O subsídio é 25 REAL-26 a partir da altura 1, com redução a cada 420.000 blocos. O gênese tem valor zero e define um domínio de assinatura próprio. O alvo inicial é o da testnet para permitir ensaios em CPU.

```bash
python3 test/functional/feature_real26_testnet.py --configfile=build/test/config.ini --ensaio --usecli
```

## Carteira desktop para a rede privada

A carteira desktop do Windows usa Python com Tk e inicia um nó REAL-26 nativo quando necessário. Ela autentica por cookie e verifica o hash do gênese antes de acessar a carteira. A rede é privada de ensaio, com RPC em loopback na porta 29826 e conexão com outros nós desativada. Os valores são de teste.

### Instalador Windows x64

Execute `REAL-26-Carteira-Ensaio-Windows-Nativa-x64.exe`. O instalador inclui o Python com Tk, o minerador e os executáveis nativos do nó. A instalação é por usuário, com o atalho **REAL-26 Carteira Nativa** na área de trabalho e no menu Iniciar. A cadeia e as carteiras ficam em `%LOCALAPPDATA%\REAL-26\No-ensaio`, fora da pasta do programa. A desinstalação preserva esses dados. Compare o SHA-256 do instalador com o arquivo `.sha256` fornecido junto dele. O pacote de ensaio ainda não tem assinatura Authenticode.

A edição nativa usa um perfil separado da edição WSL. O primeiro início cria uma cadeia de ensaio a partir do gênese. O backup da edição anterior pode recuperar o endereço e as chaves na carteira nativa. Para consultar e gastar os saldos de ensaio acumulados no WSL, abra o atalho da edição anterior, que conserva a cadeia correspondente.

### Compilar e empacotar a edição nativa

Use Linux com MinGW-w64 POSIX, CMake e Ninja. Mantenha a árvore de fontes em um sistema de arquivos Linux e confira a revisão da liboqs indicada na seção de dependências. Ajuste `liboqs` para apontar à cópia dessa dependência. [Guia de compilação para Windows do Bitcoin Core](doc/build-windows.md)

```bash
make -C depends HOST=x86_64-w64-mingw32 NO_QT=1 NO_ZMQ=1 -j 8
cmake -S liboqs -B build-oqs-windows -G Ninja \
  -DCMAKE_SYSTEM_NAME=Windows -DCMAKE_SYSTEM_PROCESSOR=x86_64 \
  -DCMAKE_C_COMPILER=x86_64-w64-mingw32-gcc-posix -DCMAKE_BUILD_TYPE=Release \
  -DOQS_USE_OPENSSL=OFF -DOQS_BUILD_ONLY_LIB=ON -DOQS_MINIMAL_BUILD=SIG_ml_dsa_65 \
  -DCMAKE_INSTALL_PREFIX="$PWD/build-oqs-windows/install"
cmake --build build-oqs-windows -j 5
cmake --install build-oqs-windows
cmake -S . -B build-native -G Ninja \
  --toolchain depends/x86_64-w64-mingw32/toolchain.cmake \
  -DBUILD_GUI=OFF -DBUILD_TESTS=OFF -DREAL26_EXPERIMENTAL_MLDSA65=ON \
  -Dliboqs_DIR="$PWD/build-oqs-windows/install/lib/cmake/liboqs" \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_EXE_LINKER_FLAGS=-static
cmake --build build-native --target bitcoind bitcoin-cli -j 7
```

No Windows, use Python x64 com Tcl/Tk e o NSIS. Passe a pasta com `bitcoind.exe` e `bitcoin-cli.exe` ao gerador. Ele grava o executável e o SHA-256 em `releases`.

```powershell
python carteira-desktop/testar_windows.py --binarios 'C:\compilacao\bin'
python carteira-desktop/gerar_instalador.py --binarios 'C:\compilacao\bin' --makensis 'C:\Program Files (x86)\NSIS\makensis.exe'
```

O teste usa um perfil temporário, bloqueia chamadas ao WSL e verifica pagamento, restauração de backup e reinício do nó.

### Executar a partir do código-fonte

```powershell
python carteira-desktop/carteira.py --binarios 'C:\compilacao\bin'
```

A interface permite criar carteiras criptografadas com nomes distintos. Use **Sair da carteira** antes de abrir outra, criar uma ou restaurar um backup. A senha é exigida antes de exibir o saldo, o histórico ou o endereço `r26e`. Ao enviar, confira o destino e a taxa calculada pela carteira antes de confirmar. As senhas passam pela entrada padrão do cliente RPC. A abertura verifica a senha, e cada envio é autorizado sem desbloquear a carteira para outras chamadas RPC. Para testar com outro nó, escolha uma pasta Windows com `--datadir` e uma porta local diferente com `--rpcport`.

A lista de atividades começa com as 50 operações mais recentes. Use **Carregar anteriores** para expandir o histórico de 50 em 50. Novas operações aparecem no topo. O carregamento de operações mais antigas conserva a posição da lista.

Nas novas carteiras, use uma senha exclusiva de pelo menos 12 caracteres. O RPC do desktop usa o cookie local e o endereço `127.0.0.1`. **Fazer backup** valida a integridade do arquivo antes de publicá-lo no destino e exige um nome novo se já houver um arquivo. Para testar a recuperação, restaure a cópia com outro nome, abra a carteira recuperada com a senha original e confira o endereço. Guarde uma cópia fora da máquina e a senha em separado.

### Perfil legado no WSL

Para abrir o perfil existente da edição anterior pelo código-fonte, execute `python carteira-desktop/carteira.py --wsl`. Esse modo usa a distribuição `REAL26-Dev`, a conta restrita `real26-wallet`, os dados em `/var/lib/real26-wallet/no` e a porta 29797. Para preparar a conta de serviço, execute a partir da raiz do projeto:

```powershell
Get-Content carteira-desktop/preparar_wsl.py -Raw | wsl -d REAL26-Dev -u root --exec python3 -
```

Se a carteira já foi usada no perfil antigo, pare a mineração e feche a janela. Encerre o nó anterior e copie a carteira e a cadeia para o perfil protegido:

```powershell
wsl -d REAL26-Dev -u root --exec /opt/real26/build/bin/bitcoin-cli -testnet4 -real26test -real26testrefs -real26ensaio -datadir=/var/lib/real26-desktop -rpcport=29797 stop
Get-Content carteira-desktop/preparar_wsl.py -Raw | wsl -d REAL26-Dev -u root --exec python3 - --migrar
```

A cópia exige o bloqueio exclusivo do perfil, preserva o original e recusa substituir um destino existente. Reabra a carteira depois da confirmação da cópia. O perfil protegido usa permissões restritas de leitura e gravação no WSL. Mantenha um backup criptografado e sua senha antes de migrar.

A recuperação por 24 palavras existe na ferramenta externa experimental. A carteira desktop atual usa o backup criptografado para recuperar a chave que já foi criada. Uma carteira determinística futura terá de derivar a chave ML-DSA-65 da frase desde a criação, com formato e versão fixados.

### Mineração por CPU ou GPU na carteira

O painel **Mineração** permite escolher **CPU**, **GPU** ou **Automático** antes de iniciar. Em CPU, cada thread selecionada usa um processo de busca. Em GPU, a carteira usa OpenCL. O modo automático verifica a GPU e passa para CPU caso ela falhe na inicialização. A carteira só começa a minerar ao clicar em **Iniciar**. Use **Encerrar** antes de trocar de modo. O painel mostra o dispositivo em uso, a taxa de hashes e quantos blocos foram aceitos na sessão.

Os dois modos usam o alvo informado pelo nó. A GPU filtra pelo prefixo do alvo, e a CPU confere o hash completo antes da submissão. O bloco parte do modelo do nó, inclui as transações selecionadas por ele e é submetido via `submitblock`. Os benchmarks históricos continuam usando seus próprios alvos de medição. As recompensas aparecem em **Recompensas a amadurecer**. Ao fechar a carteira, a busca é encerrada.

## Base de desenvolvimento

A base é o [Bitcoin Core 32.1](https://github.com/bitcoin/bitcoin/releases/tag/v32.1), revisão `f0de87f040621468b956f01f526a43a010310501`. A branch pública de desenvolvimento da REAL-26 é `main`. A licença e os avisos de autoria estão em [COPYING](COPYING).

O desenvolvimento começa em `regtest`, uma rede local com mineração sob demanda. A rede planejada terá gênese e identificadores próprios, intervalo-alvo de 10 minutos e orçamento inicial de 4 milhões de unidades de peso por bloco. A rede de desenvolvimento usa ML-DSA-65 para autorizar gastos.

## Rede de desenvolvimento

Com o suporte experimental compilado, selecione o modo da REAL-26 com `-regtest -real26dev` tanto no `bitcoind` quanto no `bitcoin-cli`. Em um arquivo de configuração, a opção `real26dev=1` pode ficar na seção `[regtest]`. A rede tem estes parâmetros:

| Parâmetro | Valor |
|---|---|
| Hash do gênese | `26df5874074ef2b195f095a7f38d13db0dbf22e11b4ab1b22d881303fc408905` |
| Mensagem da coinbase | `REAL-26 \| Rede de desenvolvimento ML-DSA-65` |
| Identificador das mensagens P2P | `b493d566` |
| Portas padrão | P2P `29744`, RPC `29743` |
| Prefixo Bech32 | `r26pq` |
| Subdiretório de dados | `real26mldsa-pq` |

O gênese de desenvolvimento tem uma saída de valor zero. Após o gênese, o modo usa as regras de mineração sob demanda de regtest. As saídas experimentais ML-DSA-65 são verificadas na mempool e no consenso deste modo. A carteira experimental de linha de comando pode assinar esses gastos em regtest. Os parâmetros da rede pública ainda estão em desenvolvimento.

## Testnet com prova de trabalho

A opção `-testnet4 -real26test` inicia uma cadeia REAL-26 independente. O nome `testnet4` seleciona a infraestrutura de teste herdada do Core. Use sempre as duas opções, no nó e no cliente RPC. Na configuração, coloque `testnet4=1` na seção global e as opções de rede em `[testnet4]`.

| Parâmetro | Valor |
|---|---|
| Hash do gênese | `000f21da01c7bb9dfb2a2e1c441c1b22587639216626312523249fc990eceaa4` |
| Identificador P2P | `b493d586` |
| Portas padrão | P2P `29764`, RPC `29763` |
| Diretório de dados da rede | `real26testnet` |
| Prefixo Bech32m | `r26t` |
| Peso máximo do bloco | 4 milhões de unidades |
| Intervalo-alvo | 5 minutos, com ajuste a cada 144 blocos |

A dificuldade inicial usa `nBits=0x1f0fffff` para viabilizar mineração em CPU. O nó verifica o trabalho de cada bloco e ajusta a dificuldade pelo tempo dos blocos anteriores. Os cinco minutos são uma média pretendida após ajuste. O RPC de mineração pode encontrar blocos mais rapidamente enquanto a dificuldade é baixa.

Os gastos exigem ML-DSA-65 com o hash do gênese da testnet no domínio da assinatura. A carteira nativa do Core permite criar endereços e assinar nesta rede. Os scripts da carteira externa continuam voltados ao regtest. A testnet começa sem sementes públicas. Use `-addnode` para indicar um par conhecido.

Para iniciar dois nós no mesmo computador, a partir da cópia de compilação Linux:

```bash
mkdir -p /tmp/real26-test-a /tmp/real26-test-b
build/bin/bitcoind -testnet4 -real26test -datadir=/tmp/real26-test-a \
  -daemonwait -bind=127.0.0.1 -listenonion=0 -discover=0 -natpmp=0
build/bin/bitcoind -testnet4 -real26test -datadir=/tmp/real26-test-b \
  -daemonwait -bind=127.0.0.1:29766 -rpcport=29765 \
  -listenonion=0 -discover=0 -natpmp=0 -addnode=127.0.0.1:29764
build/bin/bitcoin-cli -testnet4 -real26test -datadir=/tmp/real26-test-b \
  -rpcport=29765 getpeerinfo
```

Crie uma carteira Core criptografada, desbloqueie-a e obtenha um endereço com `getreal26address`. Use `generatetoaddress 101 ENDERECO 10000000` para minerar em CPU e amadurecer a primeira recompensa. Use `sendreal26 ENDERECO_DO_DESTINATARIO 1 0.0001` para enviar uma moeda e mine mais um bloco para confirmar o pagamento. A suíte abaixo automatiza o teste e verifica o ajuste de dificuldade, a reorganização e a retomada da sincronização após reinício.

```bash
python3 build/test/functional/test_runner.py feature_real26_testnet.py feature_real26_regtest.py --jobs=1
```

### Variante da testnet com referências ML-DSA-65

Inicie o nó e o cliente RPC com `-testnet4 -real26test -real26testrefs`. A variante tem limite de 4 milhões de unidades de peso, alvo de 5 minutos e ajuste de dificuldade a cada 144 blocos. A carteira nativa usa a referência canônica quando várias entradas gastam saídas da mesma chave.

| Parâmetro | Valor |
|---|---|
| Gênese e domínio das assinaturas | `00008e6fbebecfe46f33a0ef6c0655cde4d796bb4638d21bf858b434d9e2e7ed` |
| Identificador P2P | `b493d587` |
| Portas padrão | P2P `29784`, RPC `29783` |
| Subdiretório de dados | `real26testrefs` |
| Prefixo Bech32m | `r26tr` |

Para conectar duas instâncias no mesmo computador, use os comandos da seção anterior com as três opções de rede. Use as portas padrão desta variante no primeiro nó e, no segundo, porta P2P 29786, porta RPC 29785 e `-addnode=127.0.0.1:29784`. Para configurar por arquivo, selecione `testnet4=1` globalmente e use `real26test=1` e `real26testrefs=1` na seção `[testnet4]`.

```bash
python3 test/functional/feature_real26_testnet.py --configfile=build/test/config.ini --refs --usecli
```

#### Carga próxima do limite com três nós

```bash
PYTHONPATH=test/functional python3 experimentos/mldsa65/carga_testnet.py   --configfile=build/test/config.ini
```

Em três processos locais no WSL, dois mineradores alternaram a submissão de três blocos de carga com prova de trabalho. Cada bloco confirmou 597 pagamentos individuais, 150 deles com duas entradas da mesma chave. Cada bloco ocupou 3.996.136 unidades de peso e 3.731.641 bytes. Um candidato com uma transação adicional excedeu o limite e foi rejeitado com `bad-blk-weight`. O validador reiniciou após a segunda rodada, retomou um bloco minerado enquanto estava desligado e confirmou o último bloco de carga.

| Altura | Submissão e sincronização das mempools | Submissão do bloco até aceitação no validador | Mensagens de bloco compacto recebidas |
|---:|---:|---:|---:|
| 104 | 11,052 s | 1,142 s | 3.878 bytes |
| 105 | 33,704 s | 1,263 s | 7.756 bytes |
| 107 | 31,422 s | 1,121 s | 3.878 bytes |

A mempool do validador continha todas as transações antes de cada bloco. A mediana da segunda etapa foi de 1,142 s. O ensaio usou rede local e minerou os blocos em sequência, com dificuldade de teste. Os 597 pagamentos por bloco equivalem a uma projeção de 1,99 TPS com blocos igualmente cheios a cada 5 minutos.

## Compilação e verificação

O ambiente local usa Ubuntu 24.04 no WSL, na distribuição `REAL26-Dev`, com disco virtual em `E:\REAL26-WSL`. O repositório editável no Windows fica em `E:\REAL-26`, e a cópia de compilação usa `/opt/real26` no sistema de arquivos Linux. As dependências do projeto estão no [guia do Bitcoin Core para Unix](doc/build-unix.md).

Com a liboqs instalada conforme a seção abaixo e o pacote `libssl-dev` disponível no Ubuntu, compile os executáveis de linha de comando no Linux e rode o teste funcional:

```bash
cd /opt/real26
cmake -S . -B build -G Ninja -DBUILD_GUI=OFF -DENABLE_IPC=OFF -DWITH_ZMQ=OFF \
  -DCMAKE_BUILD_TYPE=Debug -DCMAKE_CXX_FLAGS_DEBUG=-g0 -DCMAKE_C_FLAGS_DEBUG=-g0 \
  -DREAL26_EXPERIMENTAL_MLDSA65=ON -Dliboqs_DIR=/opt/real26-liboqs/mldsa65/lib/cmake/liboqs
cmake --build build --target bitcoind bitcoin-cli real26_mldsa65_sign_test -j 4
python3 test/functional/feature_real26_regtest.py --configfile=build/test/config.ini
```

O teste parte de dois nós no gênese da REAL-26 e de um nó no regtest do Bitcoin. Exige que os nós REAL-26 sincronizem três blocos e verifica que o nó Bitcoin rejeita o endereço, o bloco e a identificação P2P da REAL-26. No mesmo teste, os nós aceitam e confirmam um gasto ML-DSA-65 válido. Um nó também recebe diretamente um bloco com o gasto adulterado e verifica sua rejeição pelo consenso.

## Dependência ML-DSA-65

A rede de desenvolvimento usa ML-DSA-65 nas saídas pós-quânticas, conforme [FIPS 204](https://csrc.nist.gov/pubs/fips/204/final). A implementação de desenvolvimento usa `mldsa-native` através da [liboqs 0.16.0](https://github.com/open-quantum-safe/liboqs/releases/tag/0.16.0), revisão `5a1a854b0dc9f2141bdc771c555ee60c37950183`, compilada apenas com esse algoritmo. A chave pública tem 1.952 bytes e a assinatura tem 3.309 bytes.

```bash
git clone --depth 1 --branch 0.16.0 https://github.com/open-quantum-safe/liboqs.git liboqs
test "$(git -C liboqs rev-parse HEAD)" = 5a1a854b0dc9f2141bdc771c555ee60c37950183
cmake -S liboqs -B liboqs/build-mldsa65 -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DOQS_USE_OPENSSL=OFF -DOQS_BUILD_ONLY_LIB=ON \
  -DOQS_MINIMAL_BUILD=SIG_ml_dsa_65 -DCMAKE_INSTALL_PREFIX="$PWD/liboqs/mldsa65"
cmake --build liboqs/build-mldsa65 -j 4
cmake --install liboqs/build-mldsa65
```

A testemunha da saída versão 2 inclui a assinatura e a chave pública. O compromisso da saída, o domínio da assinatura e o gênese são verificados na regra de gasto. Use uma nova carteira para a rede ML-DSA-65.

## Carteira nativa do Core

O nó com ML-DSA-65 habilitado oferece os seguintes RPCs de carteira nas redes `-regtest -real26dev` e `-testnet4 -real26test`:

| RPC | Operação |
|---|---|
| `getreal26address` | Gera um endereço ML-DSA-65 na primeira chamada. Depois retorna o endereço já registrado. |
| `sendreal26 ENDERECO VALOR TAXA` | Seleciona saídas ML-DSA-65 confirmadas e maduras, assina, devolve o troco ao endereço ML-DSA-65 da carteira e envia a transação. Valor e taxa total são em moedas. |
| `sendreal26many JSON TAXA` | Paga vários endereços ML-DSA-65 com uma única transação e troco automático. A taxa total e os valores são em moedas. |

Use uma carteira do Core criptografada com chaves privadas habilitadas. Desbloqueie-a com `walletpassphrase` para gerar a chave pela primeira vez ou enviar um pagamento. `walletlock` volta a impedir gastos. A chave ML-DSA-65 é armazenada cifrada no banco da carteira, usando a chave mestra do Core. O endereço é acompanhado por um descritor público.

Nesta versão experimental, cada carteira do Core tem um endereço ML-DSA-65. Use `sendreal26` para um destinatário e `sendreal26many` para pagamentos em lote. Os comandos genéricos do Core e o aplicativo gráfico ainda precisam de integração específica para ML-DSA-65. O endereço criado no Core tem sua própria chave. A carteira externa tem um arquivo e uma frase de recuperação próprios.

## Carteira experimental

No Ubuntu `REAL26-Dev`, instale `python3-cryptography` e `python3-mnemonic` caso essas bibliotecas estejam ausentes. Use a compilação ML-DSA-65 descrita acima e execute, em um terminal Linux na raiz do projeto:

```bash
python3 experimentos/mldsa65/carteira.py criar ./carteira-r26.enc
python3 experimentos/mldsa65/carteira.py endereco ./carteira-r26.enc
python3 experimentos/mldsa65/carteira.py assinar ./carteira-r26.enc HEX_SEM_ASSINATURAS --datadir /caminho/dos/dados
```

A carteira gera um endereço Bech32m `r26pq1z…` e cifra o par de chaves com AES-256-GCM. A chave de cifragem é derivada da senha com scrypt e sal aleatório. O arquivo criptografado pode ser copiado para backup. Guarde a senha separadamente.

Para assinar, a ferramenta consulta as saídas referenciadas em um nó REAL-26 local e exibe valores e taxa. As entradas precisam pertencer à chave da carteira.

Para montar o pagamento automaticamente, informe valores e taxas em unidades mínimas, com 100 milhões de unidades por moeda. A seleção começa pelas maiores saídas confirmadas, desconsidera recompensas imaturas e devolve o troco ao próprio endereço ML-DSA-65. Antes de devolver o hexadecimal assinado, a ferramenta consulta a política da mempool. O envio continua separado, via `sendrawtransaction`.

```bash
python3 experimentos/mldsa65/carteira.py pagar ./carteira-r26.enc ENDERECO_DESTINO 100000000 \
  --taxa 10000 --datadir /caminho/dos/dados
```

Para acompanhar saldo e transações no Core, crie uma carteira sem chaves privadas e importe somente o endereço público. A importação consulta o histórico e requer que os blocos necessários estejam disponíveis.

```bash
build/bin/bitcoin-cli -regtest -real26dev -datadir=/caminho/dos/dados \
  -named createwallet wallet_name=observacao-real26 disable_private_keys=true blank=true
python3 experimentos/mldsa65/carteira.py observar ENDERECO_MLDSA65 \
  --carteira-core observacao-real26 --datadir /caminho/dos/dados
build/bin/bitcoin-cli -regtest -real26dev -datadir=/caminho/dos/dados \
  -rpcwallet=observacao-real26 getbalance
```

A ferramenta funciona em regtest e usa uma chave por arquivo. Para carteiras criadas com o comando `criar`, use uma cópia do arquivo criptografado com a senha original. As carteiras criadas com `criar-com-frase` também podem ser restauradas somente com as 24 palavras e uma nova senha para o arquivo:

```bash
python3 experimentos/mldsa65/carteira.py criar-com-frase ./carteira-r26.enc
python3 experimentos/mldsa65/carteira.py restaurar ./carteira-restaurada.enc
```

A frase deve ser gerada pela ferramenta, mantida em segredo e guardada separadamente. O formato experimental usa a lista oficial em inglês do [BIP39](https://bips.dev/39/) e sua soma de verificação para representar 256 bits de entropia. A derivação da chave é da REAL-26. A versão 1 aplica SHAKE256 à etiqueta `REAL26/MLDSA65/WalletSeed/v1`, a um byte zero e à entropia de 32 bytes. Os 32 bytes resultantes alimentam a geração de chaves ML-DSA-65 da liboqs 0.16.0. Guarde a versão de derivação junto com as instruções do backup. Carteiras anteriores geradas sem frase continuam dependentes do arquivo criptografado.

O Core acompanha o saldo em modo de observação. O executável local em C++ gera a chave ML-DSA-65, cria e abre o envelope AES-256-GCM v2 e monta a testemunha. Na criação e na restauração, a interface em Python recebe a chave pública e o envelope cifrado, que grava sem sobrescrever um arquivo existente. Durante a assinatura, envia o envelope cifrado, a senha e os dados da transação ao assinador. O envelope v2 é próprio da rede ML-DSA-65. O OpenSSL é uma dependência do assinador local. O modo de observação continua disponível para acompanhar, no Core, as chaves geradas pela carteira externa.

## Teste em duas máquinas virtuais

O [experimento de rede virtual](experimentos/rede-virtual/testar.sh) inicia duas VMs Ubuntu em QEMU. Cada convidado usa dois processadores virtuais, 1.400 MiB de memória e um disco de dados próprio. O enlace Ethernet entre os convidados fica no computador hospedeiro. Os binários da REAL-26 são montados por uma imagem de leitura e executados em `-regtest -real26dev`.

No ambiente `REAL26-Dev`, com QEMU, KVM, `cloud-image-utils` e `genisoimage` disponíveis, o teste pode ser repetido a partir da cópia de compilação. Use uma [imagem Ubuntu Cloud Minimal 24.04](https://cloud-images.ubuntu.com/minimal/releases/noble/release/) qcow2 com o SHA-256 conferido.

```bash
cd /opt/real26
bash experimentos/rede-virtual/testar.sh /opt/real26-vms/ubuntu-noble.img build/bin
```

A segunda VM coordena a medição e consulta os dois nós por RPC. O teste mede o tempo de envio dos pagamentos, espera que todos cheguem à segunda mempool e depois minera sob demanda. A janela de inclusão termina quando a segunda VM valida o bloco e adota seu hash. São três rodadas por lote, com 1, 25 e 100 pagamentos. As medianas e os logs ficam no diretório informado pelo script.

### Carga próxima do limite em enlace simulado

Acrescente `carga` ao fim do comando para executar três blocos consecutivos de 680 pagamentos ML-DSA-65. Um retransmissor entre as interfaces virtuais aplica 25 ms de atraso e 20 Mbit/s por sentido. O cenário simula cerca de 50 ms de ida e volta e usa banda nominal de 20 Mbit/s em cada direção, sem perdas configuradas. A latência observada é conferida com um RPC leve entre os convidados.

```bash
bash experimentos/rede-virtual/testar.sh /opt/real26-vms/ubuntu-noble.img build/bin carga
```

Cada pagamento usa uma entrada, uma saída de destino e uma saída de troco. O teste separa a assinatura local, a submissão ao minerador, a espera de até 30 segundos pela segunda mempool e a inclusão em bloco. O teste registra quantas transações o segundo nó já tinha antes da mineração. As transações são assinadas pelo executável de teste e submetidas ao minerador em lotes RPC. A propagação entre os nós usa a política P2P padrão. O teste confere a presença dos 680 pagamentos no segundo nó e exige que cada bloco use entre 95% e 100% do orçamento de quatro milhões de unidades de peso.

### Blocos maiores com a mempool receptora vazia

Compile uma versão de medição separada. O binário de 15 milhões exige `-regtest -real26dev` e usa outro identificador P2P, outras portas e o diretório de dados `real26bench15m-pq` (P2P `b493d576`).

```bash
cmake -S . -B build-15m -G Ninja -DBUILD_GUI=OFF -DENABLE_IPC=OFF \
  -DREAL26_EXPERIMENTAL_MLDSA65=ON -DREAL26_BENCH_15M=ON \
  -DCMAKE_BUILD_TYPE=Debug -DCMAKE_CXX_FLAGS_DEBUG=-g0 -DCMAKE_C_FLAGS_DEBUG=-g0 \
  -Dliboqs_DIR=/opt/real26-liboqs/mldsa65/lib/cmake/liboqs
cmake --build build-15m --target bitcoind bitcoin-cli real26_mldsa65_sign_test -j 5
bash experimentos/rede-virtual/testar.sh /opt/real26-vms/ubuntu-noble.img build-15m/bin frio
```

Nesse modo, o receptor usa `-blocksonly=1`. O minerador monta blocos com pagamentos assinados, valida cada bloco localmente e o anuncia ao par. A medição verifica a mempool vazia antes da transmissão, a adoção do mesmo hash no receptor e os bytes P2P de `block`, `cmpctblock` e `blocktxn`. O perfil usa o mesmo enlace de 25 ms de atraso e 20 Mbit/s por sentido.

A comparação usa duas VMs QEMU/KVM no mesmo computador, com dois processadores virtuais e 1.400 MiB de memória por VM. Foram três rodadas intercaladas, com um bloco de cada tamanho por rodada. O mesmo binário experimental validou os três tamanhos. Cada pagamento teve uma entrada, uma saída de destino, uma saída de troco e uma assinatura ML-DSA-65. O receptor recebeu os nove blocos inteiros em mensagens P2P `block`, com a mempool vazia. O RPC leve entre as VMs teve mediana de 60,19 ms.

| Orçamento de peso | Pagamentos por bloco | Peso real | Tamanho do bloco | Da submissão à aceitação no par (mediana / máximo) | Da aceitação local à aceitação no par (mediana) | TPS projetados a cada 5 min |
|---:|---:|---:|---:|---:|---:|---:|
| 4 milhões | 685 | 3.986.270 | 3,70 MB | 3,77 s / 3,91 s | 2,70 s | 2,28 |
| 10 milhões | 1.710 | 9.949.720 | 9,25 MB | 8,86 s / 9,05 s | 6,42 s | 5,70 |
| 15 milhões | 2.570 | 14.953.200 | 13,90 MB | 13,47 s / 13,58 s | 9,55 s | 8,57 |

A primeira medição de tempo começa na chamada `submitblock` com o bloco já assinado e termina quando o receptor adota o mesmo hash. Os TPS dividem os pagamentos do bloco por 300 segundos e pressupõem blocos cheios nesse intervalo. O ensaio foi feito em regtest, com um perfil de enlace e sem perdas configuradas. A testnet usa o limite de 4 milhões.

O log bruto da execução de 19 de novembro de 2026 está em `/opt/real26-vms/teste.dec5hN7B/no-1.teste` na distribuição WSL `REAL26-Dev`. A linha `REAL26_RESULTADO` contém as nove amostras em JSON.

### Blocos mistos com e sem transações na mempool receptora

```bash
bash experimentos/rede-virtual/testar.sh /opt/real26-vms/ubuntu-noble.img build/bin misto
```

A compilação normal de regtest validou seis blocos ML-DSA-65 de 3.982.508 unidades de peso em duas VMs QEMU/KVM no mesmo computador, com 25 ms de atraso e 20 Mbit/s por sentido. Em cada bloco, 302 transações individuais e 302 lotes de dez destinatários somaram 604 transações e 3.322 pagamentos. Cada transação gastou uma entrada e teve uma assinatura. O troco fica fora da contagem de pagamentos.

| Mempool receptora | Amostras | Submissão até aceitação no receptor (mediana / máximo) | Aceitação local até aceitação no receptor (mediana) | Bytes de mensagens P2P do bloco |
|---|---:|---:|---:|---:|
| Vazia | 3 | 3,378 s / 3,898 s | 2,461 s | 3.386.675 |
| Com as 604 transações | 3 | 1,160 s / 1,170 s | 0,144 s | 3.917 |

O tempo começa no envio do bloco assinado ao minerador e termina quando o receptor adota o hash. Com a mempool vazia, o receptor solicitou as transações após receber o bloco compacto. Quando a mempool já tinha as 604 transações, a mensagem compacta foi suficiente. O tempo separado de submissão das transações ao minerador e preenchimento da mempool receptora teve mediana de 31,669 s. Os bytes acima somam as mensagens `block`, `cmpctblock` e `blocktxn` durante a propagação de cada bloco.

A carga mista projeta 11,07 pagamentos por segundo e 2,01 transações por segundo com blocos cheios a cada cinco minutos. O ensaio anterior com pagamentos individuais confirmou 685 pagamentos por bloco de tamanho semelhante, o equivalente a 2,28 pagamentos por segundo no mesmo intervalo. Os valores projetados pressupõem essa composição de pagamentos e esse intervalo.

O log bruto de 20 de novembro de 2026 está em `/opt/real26-vms/teste.5Q6gR37g/no-1.teste` na distribuição WSL `REAL26-Dev`.

### Carga com 80% de transações individuais

```bash
bash experimentos/rede-virtual/testar.sh /opt/real26-vms/ubuntu-noble.img build/bin misto80
```

Cada bloco teve 520 transações individuais e 130 lotes de dez destinatários, totalizando 650 transações, 1.820 pagamentos, 3.983.880 unidades de peso e 3.565.122 bytes. A dezena de destinatários por lote e a proporção de 80% de transações individuais definem um cenário sintético. A projeção para blocos cheios a cada cinco minutos é de 6,07 pagamentos por segundo e 2,17 transações por segundo.

O ensaio usou duas VMs QEMU/KVM no mesmo computador, em regtest, com enlace de 20 Mbit/s e atraso de 25 ms por sentido. Foram duas amostras para cada nível de cobertura, com a mesma proporção de individuais e lotes no subconjunto enviado antes do bloco.

| Transações do bloco já na mempool receptora | Submissão até aceitação no receptor (mediana / máximo) | Dados P2P das mensagens do bloco | Submissão e distribuição prévia (mediana) |
|---|---:|---:|---:|
| 0 de 650 | 3,840 s / 4,138 s | 3.569.109 bytes | — |
| 325 de 650 | 2,553 s / 2,553 s | 1.786.679 bytes | 11,514 s |
| 650 de 650 | 1,117 s / 1,136 s | 4.193 bytes | 39,866 s |

O receptor reconstruiu todos os blocos a partir da mensagem compacta e solicitou apenas as transações ausentes, quando necessário. Os tempos de propagação começam na submissão do bloco já assinado. O log bruto está em `/opt/real26-vms/teste.5pgQVrtG/no-1.teste` na distribuição WSL `REAL26-Dev`.

### Referências a chaves públicas repetidas

```bash
PYTHONPATH=test/functional python3 experimentos/mldsa65/chaves_repetidas.py
```

O ensaio assina transações ML-DSA-65 para o regtest e mede uma representação experimental que substitui cada cópia posterior da chave pública por um índice de um byte para a primeira entrada que a incluiu. Cada entrada conserva a assinatura original. O ensaio reconstrói e confere as testemunhas originais em memória. O controle com chaves distintas mede apenas o formato serializado. A codificação proposta foi avaliada fora do consenso.

| Entradas com a mesma chave | Peso atual | Peso experimental | Bytes poupados |
|---:|---:|---:|---:|
| 1 | 5.818 | 5.818 | 0 |
| 2 | 11.250 | 9.297 | 1.953 |
| 3 | 16.682 | 12.776 | 3.906 |
| 5 | 27.546 | 19.734 | 7.812 |
| 10 | 54.706 | 37.129 | 17.577 |

A carteira nativa usa a mesma chave ao selecionar várias saídas do seu endereço ML-DSA-65. A frequência de transações com múltiplas entradas depende dos saldos fragmentados e dos valores enviados. A carga em VMs usou uma entrada por transação. Em um cenário hipotético com 25% das transações gastando duas entradas com a mesma chave e 75% gastando uma entrada, a projeção passa de 1,86 para 1,99 TPS. O cálculo usa um destinatário e troco, blocos cheios de até 4 milhões de unidades, reserva de 1.000 unidades por bloco e intervalo de 5 minutos.

No bloco de laboratório com 555 transações assinadas, 139 delas com duas entradas da mesma chave, a codificação reduziu o tamanho serializado de 3.739.099 para 3.467.632 bytes e o peso de 3.984.982 para 3.713.515 unidades. O ensaio conferiu a reconstrução das testemunhas originais e repetiu o processamento 31 vezes no WSL. A mediana foi de 0,354 ms e o maior tempo foi de 0,518 ms. Essa medição cobre apenas a resolução das referências em memória. A redução de 271.467 bytes equivale a 0,109 s de transmissão nominal em um enlace de 20 Mbit/s, quando se envia o bloco inteiro com a mesma carga.

#### Aceitação e propagação em dois nós

O modo `-regtest -real26dev -real26refs` agora usa o diretório `real26refs-v2`, identificador P2P `b493d597`, porta P2P 29774 e RPC 29773. O gênese `3259f716dc16d1f59dd6b05a245a5ac268a1c8bc788e3304878bc0a0bc873405` define o domínio de assinatura do laboratório. Essa alteração inicia uma cadeia nova, separada dos dados do experimento anterior.

O ensaio atual valida e propaga blocos na versão canônica. A comparação entre os dois formatos abaixo foi feita na versão anterior do laboratório.

```bash
bash experimentos/rede-virtual/testar.sh /opt/real26-vms/ubuntu-noble.img build/bin refs
```

Em duas VMs no mesmo computador, com 25 ms de atraso e 20 Mbit/s por sentido, os nós aceitaram três blocos por formato. Cada bloco tinha 555 pagamentos, dos quais 139 usavam duas entradas da mesma chave. A mempool receptora estava vazia e os seis blocos foram recebidos inteiros por P2P. A medição começa na submissão do bloco já assinado ao primeiro nó.

| Formato | Bytes por bloco | Peso | Submissão até aceitação no par (mediana / máximo) | Aceitação local até aceitação no par (mediana) |
|---|---:|---:|---:|---:|
| Chaves completas | 3.739.098 | 3.984.978 | 3,726 s / 3,778 s | 2,753 s |
| Com referências | 3.467.631 | 3.713.511 | 3,548 s / 3,661 s | 2,618 s |

O laboratório aceitou uma referência válida na política de mempool e verificou assinaturas e compromissos de chave em cada entrada. A mempool e o consenso rejeitaram referências à própria entrada, a uma entrada futura, a um índice inexistente e uma assinatura adulterada. O teste funcional do regtest normal verifica a rejeição da codificação com referências. O log bruto está em `/opt/real26-vms/teste.3U1aDV3O/no-1.teste` na distribuição WSL `REAL26-Dev`.

#### Variantes da testemunha na mempool e em blocos compactos

Na versão anterior do laboratório, o teste com dois nós e um par P2P instrumentado confirmou que as duas representações têm o mesmo `txid` e `wtxid` diferentes. Na mempool, a primeira versão aceita permanece e a segunda é rejeitada como duplicata dos dados sem testemunha.

Quando a mempool do receptor tinha a versão com chave completa e o bloco trazia a referência, o receptor pediu em `getblocktxn` somente a posição da transação divergente, recebeu a testemunha minerada em `blocktxn` e aceitou o bloco. O teste também confirmou o sentido inverso. Quando as testemunhas coincidiam, o receptor reconstruiu o bloco compacto com a mempool. Nas três rodadas, o bloco confirmado preservou a testemunha minerada e a transação saiu da mempool.

#### Revisão interna do consenso experimental

O índice de um byte só referencia uma entrada anterior da mesma transação com chave completa de 1.952 bytes. A resolução faz uma consulta direta, sem seguir outras referências. Para cada entrada, o interpretador compara o SHA-256 da chave resolvida ao compromisso da saída gasta e verifica a assinatura ML-DSA-65 daquela entrada. O resumo assinado vincula o índice da entrada, as saídas anteriores e seus valores, as sequências e todas as saídas novas. O cache de scripts usa o `wtxid` e as flags de validação. O compromisso de testemunha vincula o bloco à variante minerada.

A versão atual exige uma codificação única para a chave de cada entrada. Se uma das primeiras 256 entradas da transação já gastou uma saída com o mesmo compromisso de chave, uma entrada posterior deve referenciar a primeira ocorrência. A comparação considera somente entradas anteriores à atual. Quando nenhuma ocorrência anterior cabe no índice de um byte, a entrada traz a chave completa. A carteira nativa aplica a mesma regra ao assinar neste laboratório.

O teste `feature_real26_refs.py` verifica o isolamento de domínio com saídas idênticas nas duas cadeias e o mesmo `txid`. Também verifica a rejeição de chaves completas redundantes na mempool e em bloco, a rejeição de referência encadeada, a reconstrução compacta com e sem a transação na mempool e o retorno da testemunha minerada à mempool ao desconectar o bloco.

Na repetição em duas VMs, a versão canônica aceitou e propagou três blocos de 555 transações, com 139 transações de duas entradas da mesma chave em cada bloco. Cada bloco pesou 3.713.511 unidades e ocupou 3.467.631 bytes. A mediana da submissão até aceitação no receptor foi de 3,528 s e o máximo foi de 3,581 s, com a mempool receptora vazia. O log bruto está em `/opt/real26-vms/teste.fmFpu4LW/no-1.teste`. As suítes do laboratório, do regtest normal e da testnet passaram.

#### Ensaio da carteira com três perfis de saldo

```bash
PYTHONPATH=test/functional python3 experimentos/mldsa65/perfis_carteira.py   --configfile=build/test/config.ini --usecli
```

O regtest normal e o laboratório receberam a mesma distribuição inicial de saídas por carteira, com 32 moedas em cada perfil. As saídas foram financiadas por recompensas de teste e amadureceram antes dos gastos. Cada carteira enviou oito pagamentos individuais e quatro lotes de dez destinatários, com o mesmo valor total, taxa e confirmação antes do gasto seguinte. A carteira pôde gastar o troco nas transações posteriores. Foram 36 transações confirmadas por formato. Em cada par de transações, o ensaio verificou a mesma contagem de entradas e saídas e a economia exata de 1.953 bytes por repetição.

| Saldo inicial | Transações com várias entradas | Peso com chaves completas → referências | Redução de peso | Transações projetadas por bloco |
|---|---:|---:|---:|---:|
| 4 saídas de 8 moedas | 0 de 12 | 76.008 → 76.008 | 0% | 631 → 631 |
| 128 saídas de 0,25 moeda | 12 de 12 | 646.368 → 441.303 | 31,73% | 74 → 108 |
| 4 saídas de 5 moedas e 48 de 0,25 | 4 de 12 | 255.264 → 190.815 | 25,25% | 187 → 251 |

A projeção usa a média de peso de cada perfil e reserva 1.000 unidades de um bloco de 4 milhões. Ela pressupõe que novos gastos tenham a mesma distribuição dos 12 observados. O ensaio representa saldos controlados, com uma chave por carteira e sem entradas novas durante a sequência de pagamentos. O log da execução está em `/tmp/real26-perfis-carteira.log` no WSL. A linha `REAL26_RESULTADO` guarda os pesos e a contagem de entradas de cada transação em JSON.

## Desempenho do ML-DSA-65

No Ubuntu de desenvolvimento, a mediana de sete lotes de 1.000 operações sobre resumos de 32 bytes foi de **166,18 µs para assinar** e **56,35 µs para verificar** com ML-DSA-65. O teste mede a biblioteca, com uma rodada de aquecimento, sem custo de carteira ou rede.

```bash
cc -O2 -I/opt/real26-liboqs/mldsa65/include experimentos/mldsa65/benchmark-assinaturas.c \
  /opt/real26-liboqs/mldsa65/lib/liboqs.a -pthread -lm -o build/bench-mldsa65
build/bench-mldsa65 ML-DSA-65
python3 experimentos/mldsa65/capacidade.py
```

A medição de capacidade serializa uma transação realmente assinada, com uma entrada ML-DSA-65 e todas as saídas pós-quânticas. Uma transação com **1 destinatário e troco** ocupa 5.407 bytes e 5.818 unidades de peso. Com **10 destinatários e troco**, ela ocupa 5.794 bytes e 7.366 unidades. O agrupamento usa cerca de 87% menos peso que dez transações desse tipo separadas, quando uma entrada tem saldo suficiente.

| Alvo de bloco | Peso máximo | TPS projetados, um destinatário por transação |
|---|---:|---:|
| 10 min | 4 milhões | 1,15 |
| 5 min | 10 milhões | 5,73 |
| 5 min | 15 milhões | 8,59 |

O nó de desenvolvimento ainda usa o limite de 4 milhões e mineração sob demanda. Os alvos de 5 minutos e os limites maiores são cenários de capacidade. A política da mempool foi testada com um lote de 10 destinatários e uma assinatura. A carteira oferece o RPC `sendreal26many` para criar e enviar lotes.

## Idioma e revisão

- Escreva em português brasileiro a documentação, os comentários novos da REAL-26 e as mensagens novas destinadas ao público brasileiro.
- Use os comentários para explicar a intenção, as restrições de consenso e as condições que os testes precisam cobrir.
- Para conservar a rastreabilidade das atualizações, preserve identificadores, comandos e comentários herdados do Bitcoin Core. Registre em português as mudanças da REAL-26.
- Documente cada mudança de consenso e inclua testes para os casos válidos e inválidos antes de integrá-la.
