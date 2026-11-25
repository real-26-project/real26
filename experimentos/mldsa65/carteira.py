#!/usr/bin/env python3
# Distribuído sob a licença MIT. Consulte o arquivo COPYING.
"""Carteira experimental ML-DSA-65 para o regtest da REAL-26."""

import argparse
from functools import partial
from decimal import Decimal
from getpass import getpass
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import unicodedata
import tempfile

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "test" / "functional"))

from test_framework.messages import COIN, COutPoint, CTransaction, CTxIn, CTxOut, ser_vector, tx_from_hex  # noqa: E402
from test_framework.segwit_addr import encode_segwit_address  # noqa: E402

GENESE = "26df5874074ef2b195f095a7f38d13db0dbf22e11b4ab1b22d881303fc408905"
FORMATO = b"REAL26-CARTEIRA-2"
TAM_PUBLICA = 1952
TAM_PRIVADA = 4032
TAM_ENVELOPE = len(FORMATO) + 16 + 12 + TAM_PUBLICA + TAM_PRIVADA + 16


def derivar(senha, sal):
    if not senha:
        raise ValueError("Informe uma senha para a carteira.")
    return hashlib.scrypt(senha.encode(), salt=sal, n=2**17, r=8, p=1,
                          maxmem=256 * 1024**2, dklen=32)


def executar_assinador(assinador, comando, dados=None):
    try:
        return subprocess.run([assinador, comando], input=dados, capture_output=True,
                              check=True).stdout
    except subprocess.CalledProcessError as erro:
        detalhe = erro.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(detalhe or "O assinador local falhou.") from erro


def criar_carteira(arquivo, senha, assinador, *, frase=None):
    dados = serializar_senha(senha)
    if frase is None:
        resposta = executar_assinador(assinador, "criar-carteira", dados)
    else:
        entropia = decodificar_frase(frase)
        semente = hashlib.shake_256(b"REAL26/MLDSA65/WalletSeed/v1\x00" + entropia).digest(32)
        resposta = executar_assinador(assinador, "restaurar-carteira-v1", dados + semente)
    publica, envelope = resposta[:TAM_PUBLICA], resposta[TAM_PUBLICA:]
    validar_envelope(envelope)
    # Publica o arquivo completo de uma vez, sem sobrescrever uma carteira.
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(dir=arquivo.parent, delete=False) as destino:
            temporario = Path(destino.name)
            destino.write(envelope)
            destino.flush()
            os.fsync(destino.fileno())
        os.link(temporario, arquivo)
    finally:
        if temporario is not None:
            temporario.unlink()
    return publica


def lista_frase():
    try:
        from mnemonic import Mnemonic
    except ImportError as erro:
        raise ValueError("Instale python3-mnemonic para usar a recuperação por frase.") from erro
    return Mnemonic("english")


def gerar_frase():
    return lista_frase().to_mnemonic(os.urandom(32))


def decodificar_frase(frase):
    palavras = unicodedata.normalize("NFKD", frase).split()
    if len(palavras) != 24:
        raise ValueError("A frase de recuperação deve ter 24 palavras.")
    lista = lista_frase()
    if not lista.check(" ".join(palavras)):
        raise ValueError("Palavra ou soma de verificação da frase inválida.")
    valor = 0
    for palavra in palavras:
        valor = (valor << 11) | lista.wordlist.index(palavra)
    # Os oito bits finais são a soma de verificação do BIP39.
    return (valor >> 8).to_bytes(32, "big")


def senha_nova():
    senha = getpass("Senha da carteira: ")
    if senha != getpass("Repita a senha: "):
        raise ValueError("As senhas são diferentes.")
    return senha


def validar_envelope(dados):
    if len(dados) != TAM_ENVELOPE or not dados.startswith(FORMATO):
        raise ValueError("Formato ou tamanho do arquivo de carteira inválido.")


def ler_envelope(arquivo):
    with arquivo.open("rb") as origem:
        dados = origem.read(TAM_ENVELOPE + 1)
    validar_envelope(dados)
    return dados


def abrir_carteira(arquivo, senha):
    dados = ler_envelope(arquivo)
    inicio = len(FORMATO)
    sal = dados[inicio:inicio + 16]
    nonce = dados[inicio + 16:inicio + 28]
    try:
        chaves = AESGCM(derivar(senha, sal)).decrypt(nonce, dados[inicio + 28:], FORMATO)
    except InvalidTag as erro:
        raise ValueError("Senha incorreta ou arquivo de carteira adulterado.") from erro
    return chaves[:TAM_PUBLICA], chaves[TAM_PUBLICA:]


def compromisso(publica):
    return hashlib.sha256(publica).digest()


def endereco(publica):
    return encode_segwit_address("r26pq", 2, compromisso(publica))


def assinar_transacao(tx, saidas_gastas, publica, privada, assinador):
    if not tx.vin or not tx.vout or not tx.wit.is_null() or any(entrada.scriptSig for entrada in tx.vin):
        raise ValueError("Forneça uma transação completa e sem assinaturas.")
    script = b"\x52\x20" + compromisso(publica)
    if len(saidas_gastas) != len(tx.vin) or any(saida.scriptPubKey != script for saida in saidas_gastas):
        raise ValueError("Todas as entradas devem gastar saídas desta carteira.")
    sem_testemunha = tx.serialize_without_witness()
    dados = publica + privada + sem_testemunha + ser_vector(saidas_gastas)
    assinado = executar_assinador(assinador, "assinar-tx", dados)
    return aplicar_testemunha(tx, sem_testemunha, assinado)


def serializar_senha(senha):
    senha_bytes = senha.encode()
    if not senha_bytes or len(senha_bytes) > 1024 * 1024:
        raise ValueError("Tamanho da senha inválido.")
    return struct.pack("<I", len(senha_bytes)) + senha_bytes


def dados_desbloqueio(arquivo, senha):
    return serializar_senha(senha) + ler_envelope(arquivo)


def abrir_publica(arquivo, senha, assinador):
    publica = executar_assinador(assinador, "abrir-publica", dados_desbloqueio(arquivo, senha))
    if len(publica) != TAM_PUBLICA:
        raise ValueError("O assinador devolveu uma chave pública de tamanho inválido.")
    return publica


def assinar_com_arquivo(tx, saidas_gastas, arquivo, senha, assinador):
    if not tx.vin or not tx.vout or not tx.wit.is_null() or any(entrada.scriptSig for entrada in tx.vin):
        raise ValueError("Forneça uma transação completa e sem assinaturas.")
    sem_testemunha = tx.serialize_without_witness()
    dados = dados_desbloqueio(arquivo, senha) + sem_testemunha + ser_vector(saidas_gastas)
    assinado = executar_assinador(assinador, "assinar-carteira", dados)
    return aplicar_testemunha(tx, sem_testemunha, assinado)


def aplicar_testemunha(tx, sem_testemunha, assinado):
    resultado = tx_from_hex(assinado.hex())
    if resultado.serialize_without_witness() != sem_testemunha or not resultado.wit.vtxinwit:
        raise ValueError("O assinador não devolveu a transação solicitada com testemunha.")
    tx.wit = resultado.wit
    return tx


def conectar_no(cli, datadir):
    def rpc(*argumentos):
        comando = [cli, "-regtest", "-real26dev", f"-datadir={datadir}", *argumentos]
        return subprocess.check_output(comando, text=True).strip()

    if rpc("getblockhash", "0") != GENESE:
        raise ValueError("O nó consultado não pertence à rede de desenvolvimento REAL-26.")
    return rpc


def saida_disponivel(rpc, txid, indice):
    dados = rpc("gettxout", txid, str(indice))
    if not dados or dados == "null":
        return None
    return json.loads(dados, parse_float=Decimal)


def converter_saida(dados):
    return CTxOut(int(dados["value"] * COIN), bytes.fromhex(dados["scriptPubKey"]["hex"]))


def consultar_saidas(tx, cli, datadir):
    rpc = conectar_no(cli, datadir)
    saidas = []
    for entrada in tx.vin:
        prev = entrada.prevout
        dados = saida_disponivel(rpc, f"{prev.hash:064x}", prev.n)
        if dados is None:
            raise ValueError("Uma saída referenciada está indisponível ou já foi gasta.")
        saidas.append(converter_saida(dados))
    return saidas


def observar(rpc, endereco_publico, nome):
    if not nome:
        raise ValueError("Informe uma carteira de observação do Core.")
    dados = json.loads(rpc("validateaddress", endereco_publico))
    if not dados["isvalid"] or dados.get("witness_version") != 2 or len(dados.get("witness_program", "")) != 64:
        raise ValueError("Forneça um endereço ML-DSA-65 da REAL-26 de desenvolvimento.")
    wallet_rpc = partial(rpc, f"-rpcwallet={nome}")
    info = json.loads(wallet_rpc("getwalletinfo"))
    if info["private_keys_enabled"]:
        raise ValueError("A carteira do Core deve ser criada com as chaves privadas desativadas.")
    descritor = json.loads(rpc("getdescriptorinfo", f"addr({endereco_publico})"))["descriptor"]
    pedido = json.dumps([{"desc": descritor, "timestamp": 0}])
    [resultado] = json.loads(wallet_rpc("importdescriptors", pedido))
    if not resultado["success"]:
        raise ValueError(resultado["error"]["message"])
    return endereco_publico


def montar_pagamento(rpc, publica, destinatario, valor, taxa):
    if valor <= 0 or taxa <= 0 or valor + taxa > 21_000_000 * COIN:
        raise ValueError("Valor ou taxa inválidos.")
    destino = json.loads(rpc("validateaddress", destinatario))
    script_destino = bytes.fromhex(destino.get("scriptPubKey", ""))
    if not destino["isvalid"] or len(script_destino) != 34 or script_destino[:2] != b"\x52\x20":
        raise ValueError("O pagamento exige um endereço ML-DSA-65 da REAL-26.")
    script_origem = b"\x52\x20" + compromisso(publica)
    pedido = json.dumps([f"raw({script_origem.hex()})"])
    resultado = json.loads(rpc("scantxoutset", "start", pedido), parse_float=Decimal)
    if not resultado["success"]:
        raise ValueError("O nó não concluiu a busca de moedas disponíveis.")
    candidatos = sorted(resultado["unspents"], key=lambda item: (-item["amount"], item["txid"], item["vout"]))
    tx = CTransaction()
    tx.version = 2
    saidas = []
    total = 0
    for candidato in candidatos:
        txid, indice = candidato["txid"], candidato["vout"]
        dados = saida_disponivel(rpc, txid, indice)
        if dados is None or dados["confirmations"] < (100 if dados["coinbase"] else 1):
            continue
        saida = converter_saida(dados)
        if saida.scriptPubKey != script_origem:
            continue
        tx.vin.append(CTxIn(COutPoint(int(txid, 16), indice)))
        saidas.append(saida)
        total += saida.nValue
        if total >= valor + taxa:
            break
    if total < valor + taxa:
        raise ValueError("Saldo confirmado e maduro insuficiente para o valor e a taxa.")
    tx.vout = [CTxOut(valor, script_destino)]
    troco = total - valor - taxa
    if troco:
        tx.vout.append(CTxOut(troco, script_origem))
    return tx, saidas


def mostrar_pagamento(tx, saidas):
    taxa = sum(s.nValue for s in saidas) - sum(s.nValue for s in tx.vout)
    if taxa < 0 or any(s.nValue < 0 for s in tx.vout):
        raise ValueError("Valores de saída ou taxa inválidos.")
    for saida in tx.vout:
        print(f"Saída: {saida.nValue} unidades mínimas, script {saida.scriptPubKey.hex()}", file=sys.stderr)
    print(f"Taxa: {taxa} unidades mínimas.", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assinador", type=Path, default=RAIZ / "build/bin/real26_mldsa65_sign_test")
    comandos = parser.add_subparsers(dest="comando", required=True)
    for comando in ("criar", "criar-com-frase", "restaurar", "endereco"):
        comandos.add_parser(comando).add_argument("arquivo", type=Path)
    assinar = comandos.add_parser("assinar")
    assinar.add_argument("arquivo", type=Path)
    assinar.add_argument("transacao", help="Transação bruta em hexadecimal, sem assinaturas.")
    pagar = comandos.add_parser("pagar", help="Seleciona moedas, calcula o troco e gera o pagamento assinado.")
    pagar.add_argument("arquivo", type=Path)
    pagar.add_argument("destinatario")
    pagar.add_argument("valor", type=int, help="Valor em unidades mínimas.")
    pagar.add_argument("--taxa", type=int, required=True, help="Taxa total em unidades mínimas.")
    acompanhar = comandos.add_parser("observar", help="Importa o endereço numa carteira de observação do Core.")
    acompanhar.add_argument("endereco_publico")
    acompanhar.add_argument("--carteira-core", required=True)
    for comando in (assinar, pagar, acompanhar):
        comando.add_argument("--datadir", type=Path, required=True)
        comando.add_argument("--cli", type=Path, default=RAIZ / "build/bin/bitcoin-cli")
    args = parser.parse_args()
    if args.comando != "observar" and not sys.stdin.isatty():
        parser.error("Abra um terminal interativo para digitar a senha.")
    try:
        if args.comando == "criar":
            print(endereco(criar_carteira(args.arquivo, senha_nova(), args.assinador)))
        elif args.comando == "criar-com-frase":
            frase = gerar_frase()
            # A frase sai apenas no terminal, longe da saída redirecionável do comando.
            with open("/dev/tty", "w", encoding="utf-8") as terminal:
                print("Anote a frase de recuperação. Ela dá acesso à carteira:", file=terminal)
                print(frase, file=terminal, flush=True)
            confirmacao = getpass("Digite as 24 palavras para confirmar: ")
            if decodificar_frase(confirmacao) != decodificar_frase(frase):
                raise ValueError("A frase de confirmação é diferente da frase gerada.")
            print(endereco(criar_carteira(args.arquivo, senha_nova(), args.assinador, frase=frase)))
        elif args.comando == "restaurar":
            frase = getpass("Digite as 24 palavras da REAL-26: ")
            decodificar_frase(frase)
            print(endereco(criar_carteira(args.arquivo, senha_nova(), args.assinador, frase=frase)))
        elif args.comando == "endereco":
            publica = abrir_publica(args.arquivo, getpass("Senha da carteira: "), args.assinador)
            print(endereco(publica))
        elif args.comando == "assinar":
            tx = tx_from_hex(args.transacao)
            if bytes.fromhex(args.transacao) != tx.serialize():
                raise ValueError("A serialização da transação contém dados inválidos ou excedentes.")
            saidas = consultar_saidas(tx, args.cli, args.datadir)
            mostrar_pagamento(tx, saidas)
            senha = getpass("Senha para autorizar o gasto: ")
            print(assinar_com_arquivo(tx, saidas, args.arquivo, senha, args.assinador).serialize().hex())
        elif args.comando == "observar":
            rpc = conectar_no(args.cli, args.datadir)
            print(observar(rpc, args.endereco_publico, args.carteira_core))
        else:
            rpc = conectar_no(args.cli, args.datadir)
            senha = getpass("Senha da carteira: ")
            publica = abrir_publica(args.arquivo, senha, args.assinador)
            tx, saidas = montar_pagamento(rpc, publica, args.destinatario, args.valor, args.taxa)
            print(f"Destino: {args.destinatario}", file=sys.stderr)
            if len(tx.vout) > 1:
                print(f"Troco: {tx.vout[1].nValue} unidades mínimas para {endereco(publica)}.", file=sys.stderr)
            mostrar_pagamento(tx, saidas)
            print("Autorizar este pagamento? [s/N] ", end="", file=sys.stderr, flush=True)
            if input().strip().lower() != "s":
                raise ValueError("Pagamento cancelado.")
            hex_assinado = assinar_com_arquivo(tx, saidas, args.arquivo, senha, args.assinador).serialize().hex()
            [resultado] = json.loads(rpc("testmempoolaccept", json.dumps([hex_assinado])))
            if not resultado["allowed"]:
                raise ValueError(f"O nó rejeitou o pagamento: {resultado['reject-reason']}")
            print(hex_assinado)
    except (EOFError, OSError, ValueError, struct.error, subprocess.CalledProcessError) as erro:
        parser.exit(1, f"Erro: {erro}\n")


if __name__ == "__main__":
    main()
