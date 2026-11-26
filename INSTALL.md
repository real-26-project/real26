# Instalação da REAL-26

## Carteira nativa no Windows

Para instalar e usar a carteira na testnet, siga o [guia da REAL-26](doc/real26/uso.md). O instalador inclui o nó nativo e o minerador.

## Nó da testnet no Ubuntu 24.04 x86_64

Baixe o pacote Ubuntu da [release oficial](https://github.com/real-26-project/real26/releases/tag/testnet-v0.2.2) e [verifique o download](README.md#verificação-dos-downloads-da-real-26). Tenha a biblioteca de execução `libsqlite3-0` instalada. Depois, extraia o pacote e entre no diretório de extração.

Use uma pasta de dados própria para o nó. O exemplo abaixo usa a lista de pares publicada no repositório. Copie o endereço atual do [arquivo de pares iniciais](carteira-desktop/pares-testnet.txt) para a variável `PAR`.

```bash
PAR=18.119.28.41:29838
DADOS="$HOME/.real26-testnet"
mkdir -p "$DADOS"

./real26d -testnet4 -real26test -real26testrefs -real26testasert \
  -noconf -datadir="$DADOS" -addnode="$PAR" -listen=0 \
  -rpcbind=127.0.0.1 -rpcport=29837 -disablewallet=1 -daemon

./real26-cli -testnet4 -real26test -real26testrefs -real26testasert \
  -noconf -datadir="$DADOS" -rpcport=29837 -rpcwait getblockchaininfo

./real26-cli -testnet4 -real26test -real26testrefs -real26testasert \
  -noconf -datadir="$DADOS" -rpcport=29837 stop
```

O pacote também inclui `real26-testnet.service` para implantação como serviço. Para aceitar conexões de outros nós, use a porta **P2P TCP 29838**. Mantenha a porta **RPC 29837** restrita ao loopback e autenticada pelo cookie.

## Compile e teste

- [Compilação e verificação da REAL-26 no Linux](README.pt-BR.md#compilação-e-verificação)
- [Dependência ML-DSA-65](README.pt-BR.md#dependência-ml-dsa-65)
- [Compilação e empacotamento da carteira Windows](README.pt-BR.md#compilar-e-empacotar-a-edição-nativa)

Após compilar com ML-DSA-65 e com o limite normal de peso, rode as oito suítes funcionais da REAL-26 a partir da raiz do repositório.

```bash
bash experimentos/verificar-candidata.sh build
```

Para validar a edição nativa, use no Windows `python carteira-desktop/testar_windows.py --binarios DIRETORIO_DOS_EXECUTAVEIS`.

## Gere o pacote Ubuntu

Depois de compilar o nó e conferir a suíte da REAL-26, gere o pacote com o serviço, os avisos de licença e o SHA-256.

```bash
python3 contrib/real26/gerar_pacote_ubuntu.py --binarios build/bin \
  --saida releases/REAL-26-No-Testnet-Ubuntu-24.04-x86_64.tar.gz
```

A automação [REAL-26](.github/workflows/real26.yml) executa as oito suítes com ML-DSA-65 e valida o pacote no Ubuntu 24.04. As execuções publicam o relatório de testes e o pacote de validação como artefatos do GitHub Actions.
