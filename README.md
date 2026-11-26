# REAL-26

<img src="carteira-desktop/real26.png" alt="Símbolo da REAL-26" width="144">

A REAL-26 é um projeto brasileiro de moeda digital de código aberto. A **testnet piloto** é uma rede P2P da REAL-26, com assinaturas ML-DSA-65, ajuste de dificuldade ASERT e meta de cinco minutos por bloco. As moedas da testnet são de teste e não têm valor monetário.

## Teste no Windows

1. Baixe o instalador **Windows x64** na [release oficial da REAL-26](https://github.com/real-26-project/real26/releases/tag/testnet-v0.2.1) e [verifique o download](#verificação-dos-downloads-da-real-26).
2. Abra **REAL-26 Carteira Nativa** e clique em **Conectar à testnet**. A carteira tenta conectar automaticamente ao nó inicial da REAL-26.
3. Crie uma carteira de teste ou escolha **Restaurar backup**. Use **Receber** para copiar seu endereço, **Enviar** para fazer um pagamento de teste ou inicie a mineração na carteira.

O **Teste isolado** roda uma cadeia local com carteiras e saldos próprios. Para interagir com outros participantes, escolha **Conectar à testnet**. A edição nativa roda diretamente no Windows.

## Documentação da REAL-26

- [Guia de uso da carteira e da testnet](doc/real26/uso.md)
- [Instalação do nó, compilação e testes](INSTALL.md)
- [Mapa do código da REAL-26](doc/real26/codigo.md)
- [Notas técnicas e resultados dos ensaios](README.pt-BR.md)
- [Como contribuir](CONTRIBUTING.md) · [Política de segurança](SECURITY.md)

## Verificação dos downloads da REAL-26

Na [release oficial](https://github.com/real-26-project/real26/releases/tag/testnet-v0.2.1), baixe `SHA256SUMS` e `SHA256SUMS.asc`. Obtenha a [chave pública da REAL-26](REAL-26-RELEASE-KEY.asc) e confirme que a impressão digital é `8BFA 04DE BE28 8B2B EBBD 3192 AA1B 07B0 3319 8941`.

```sh
gpg --show-keys --fingerprint REAL-26-RELEASE-KEY.asc
gpg --import REAL-26-RELEASE-KEY.asc
gpg --verify SHA256SUMS.asc SHA256SUMS
```

Compare o SHA-256 do download com o manifesto verificado. No PowerShell, use `Get-FileHash -Algorithm SHA256 CAMINHO_DO_ARQUIVO`. No Linux, use `sha256sum CAMINHO_DO_ARQUIVO`. O instalador Windows desta prévia ainda está sem assinatura Authenticode.

## Licença e origem

A REAL-26 deriva do Bitcoin Core 32.1. Consulte [COPYING](COPYING) para a licença MIT e os avisos de autoria, e [licenças do nó](licencas/) para os componentes incorporados.
