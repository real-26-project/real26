# Licenças dos componentes do nó REAL-26

O código da REAL-26 e a base Bitcoin Core usam a licença MIT. Consulte `COPYING` na raiz do repositório ou do pacote.

- **liboqs 0.16.0** usa MIT como licença geral. A compilação do nó usa a revisão `5a1a854b0dc9f2141bdc771c555ee60c37950183`, com ML-DSA-65. O aviso original está em `liboqs-0.16.0.txt`.
- **mldsa-native** é incorporado pela liboqs. As opções de licença para a implementação são Apache-2.0, ISC ou MIT. O texto upstream da revisão `9b0ee84f4cf399043eca59eca4e5f8531ca1d61b` está em `mldsa-native.txt`.
- **XKCP** fornece implementações de Keccak à liboqs. As implementações usadas declaram CC0 1.0 em seus cabeçalhos. Consulte `src/common/sha3/xkcp_low` na revisão da liboqs indicada acima.
- **LevelDB, CRC32C, Minisketch e libsecp256k1** vêm do Bitcoin Core. Seus avisos estão nos arquivos `leveldb.txt`, `crc32c.txt`, `minisketch.txt` e `secp256k1.txt` do pacote, e nos arquivos de licença dos respectivos diretórios em `src/` no repositório.
- **UniValue** usa MIT. Inclui contribuições de BitPay Inc. (2014), Wladimir J. van der Laan (2016) e desenvolvedores do Bitcoin Core. Consulte os cabeçalhos em `src/univalue` e o texto em `COPYING`.
- **SQLite** é de domínio público segundo a documentação do projeto. O pacote Ubuntu usa a biblioteca do sistema.
