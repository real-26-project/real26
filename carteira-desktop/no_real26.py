# Distribuído sob a licença MIT. Consulte COPYING.
"""Acesso local ao nó de ensaio, com autenticação pelo cookie do Core."""

from decimal import Decimal, InvalidOperation, ROUND_CEILING
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
from tempfile import TemporaryDirectory
from time import monotonic, sleep


GENESE = "0007326bf77a1489a5e6ee7aa98affe5baac14aa7f2b694a86e2b54c8ae24733"
BASE_TESTNET = ("-testnet4", "-real26test", "-real26testrefs")
REDE = (*BASE_TESTNET, "-real26ensaio")
REDE_COMPARTILHADA = (*BASE_TESTNET, "-real26testasert")
GENESE_COMPARTILHADO = "0000058319331d5a63c4d88f6338cce3b9deb43110246e701b4508dc4c15b2c2"
WSL = ("wsl.exe", "-d", "REAL26-Dev", "-u", "real26-wallet", "--exec")
DADOS = "/var/lib/real26-wallet/no"
LEGADO = "/var/lib/real26-desktop"
BINARIOS = "/opt/real26/build/bin"
PORTA_WSL = 29797
PORTA_WINDOWS = 29826
PORTA_RPC_COMPARTILHADA = 29837
CARTEIRA = "real26-desktop"
CASA_DECIMAL = Decimal("0.00000001")
MINIMO_SENHA_NOVA = 12


class ErroNo(RuntimeError):
    pass


class SenhaIncorreta(ErroNo):
    pass


class NoReal26:
    def __init__(self, datadir=None, porta=None, *, binarios=None, pares=(), compartilhado=False):
        self.nativo = binarios is not None
        self.pares = tuple(self.validar_par(par) for par in pares)
        self.compartilhado = compartilhado or bool(self.pares)
        self.genese = GENESE_COMPARTILHADO if self.compartilhado else GENESE
        self.prefixo_destino = "r26s1z" if self.compartilhado else "r26e1z"
        perfil = "No-testnet-ASERT-v2" if self.compartilhado else "No-ensaio"
        if self.nativo:
            pasta = Path(binarios).resolve()
            self.cli = str(pasta / "bitcoin-cli.exe")
            self.no = str(pasta / "bitcoind.exe")
            self.datadir = Path(datadir or Path(os.environ["LOCALAPPDATA"]) / "REAL-26" / perfil).resolve()
        else:
            self.cli = f"{BINARIOS}/bitcoin-cli"
            self.no = f"{BINARIOS}/bitcoind"
            self.datadir = datadir or DADOS
        if self.nativo and self.compartilhado:
            self.arquivo_pares = self.datadir / "pares-testnet.txt"
            salvos = self.ler_pares_iniciais(self.arquivo_pares)
            self.pares = tuple(dict.fromkeys((*self.pares, *salvos)))
        porta_padrao = PORTA_WINDOWS if self.nativo else PORTA_WSL
        if self.compartilhado:
            porta_padrao = PORTA_RPC_COMPARTILHADA
        rede = REDE_COMPARTILHADA if self.compartilhado else REDE
        self.opcoes = (*rede, "-noconf", f"-datadir={self.datadir}", f"-rpcport={porta or porta_padrao}")
        self.processo = None
        self.carteira = None
        self.carteira_propria = False

    @staticmethod
    def validar_par(par):
        par = par.strip().lower()
        if par == "0" or not re.fullmatch(r"[A-Za-z0-9.\-:\[\]]{1,255}", par):
            raise ErroNo("Informe um endereço de nó ou IP válido.")
        return par

    @classmethod
    def ler_pares_iniciais(cls, caminho):
        try:
            linhas = caminho.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return ()
        pares = (linha.partition("#")[0].strip() for linha in linhas)
        return tuple(dict.fromkeys(cls.validar_par(par) for par in pares if par))

    def adicionar_par(self, par):
        par = self.validar_par(par)
        registrados = self.rpc("getaddednodeinfo")
        if par not in {registro["addednode"] for registro in registrados}:
            self.rpc("addnode", par, "add")
        if par not in self.ler_pares_iniciais(self.arquivo_pares):
            with self.arquivo_pares.open("a", encoding="utf-8") as arquivo:
                arquivo.write(f"{par}\n")

    def executar(self, argumentos, entrada=None, timeout=30):
        comando = argumentos if self.nativo else (*WSL, *argumentos)
        try:
            processo = subprocess.run(
                comando,
                input=entrada,
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=timeout,
            )
        except FileNotFoundError as erro:
            raise ErroNo("Instale o nó da REAL-26 ou confira o caminho dos executáveis.") from erro
        if processo.returncode:
            mensagem = processo.stderr.decode("utf-8", errors="replace").replace("\x00", "").strip()
            if "error code: -14" in mensagem.splitlines():
                raise SenhaIncorreta("A senha da carteira está incorreta. Digite-a novamente.")
            raise ErroNo(mensagem or "O nó local não respondeu.")
        return processo.stdout.decode("utf-8", errors="replace").strip()

    def rpc(self, metodo, *args, carteira=False):
        parametros = []
        for arg in args:
            if isinstance(arg, str):
                if "\n" in arg or "\r" in arg or "\x00" in arg:
                    raise ErroNo("Use apenas uma linha em cada campo.")
                parametros.append(arg)
            else:
                parametros.append(json.dumps(arg, ensure_ascii=False))
        if carteira and self.carteira is None:
            raise ErroNo("Abra uma carteira primeiro.")
        rota = (f"-rpcwallet={self.carteira}",) if carteira else ()
        entrada = ("\n".join(parametros) + "\n").encode("utf-8") if parametros else None
        stdin = ("-stdin",) if entrada is not None else ()
        saida = self.executar((self.cli, *self.opcoes, "-rpcconnect=127.0.0.1", *rota, *stdin, metodo), entrada)
        try:
            return json.loads(saida, parse_float=Decimal) if saida else None
        except json.JSONDecodeError:
            return saida

    def conectar(self):
        try:
            genese = self.rpc("getblockhash", 0)
        except ErroNo:
            genese = self.iniciar_no()
        if genese != self.genese:
            self.carteira = None
            self.carteira_propria = False
            raise ErroNo("O gênese do nó difere do gênese do perfil selecionado.")
        if self.carteira is not None and self.carteira not in self.rpc("listwallets"):
            self.carteira = None
            self.carteira_propria = False

    def iniciar_no(self):
        conexoes = tuple(f"-addnode={par}" for par in self.pares) if self.compartilhado else ("-connect=0",)
        argumentos = (
            self.no,
            *self.opcoes,
            "-listen=0",
            *conexoes,
            "-dnsseed=0",
            "-fixedseeds=0",
            "-rpcbind=127.0.0.1",
            "-onion=0",
            "-listenonion=0",
            "-discover=0",
        )
        if not self.nativo:
            if (
                self.datadir == DADOS
                and self.executar(
                    (
                        "sh",
                        "-c",
                        'if [ -d "$1" ] && [ ! -d "$2" ]; then printf migrar; fi',
                        "real26",
                        LEGADO,
                        DADOS,
                    )
                )
                == "migrar"
            ):
                raise ErroNo("Existe um perfil anterior. Faça a migração protegida descrita no README.")
            self.executar(("mkdir", "-m", "700", "-p", "--", self.datadir))
            self.executar((*argumentos, "-daemonwait"), timeout=60)
            return self.rpc("getblockhash", 0)

        if not Path(self.no).is_file() or not Path(self.cli).is_file():
            raise ErroNo("Os executáveis nativos do nó REAL-26 não foram encontrados.")
        self.datadir.mkdir(parents=True, exist_ok=True)
        registro = self.datadir / "inicializacao.log"
        if self.processo is None or self.processo.poll() is not None:
            with registro.open("ab") as log:
                try:
                    self.processo = subprocess.Popen(
                        argumentos,
                        stdin=subprocess.DEVNULL,
                        stdout=log,
                        stderr=log,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                except OSError as erro:
                    raise ErroNo(f"O Windows não conseguiu executar o nó REAL-26: {erro}") from erro
        prazo = monotonic() + 60
        while monotonic() < prazo:
            try:
                return self.rpc("getblockhash", 0)
            except (ErroNo, subprocess.TimeoutExpired) as erro:
                if self.processo.poll() is not None:
                    raise ErroNo(f"O nó REAL-26 encerrou ao iniciar. Consulte {registro}.") from erro
                sleep(0.2)
        raise ErroNo(f"O nó REAL-26 ainda não respondeu. Consulte {registro}.")

    def encerrar_no_proprio(self):
        if self.processo is not None and self.processo.poll() is None:
            try:
                self.conferir_genese()
                self.rpc("stop")
            except (ErroNo, subprocess.TimeoutExpired):
                # Preserve o banco da carteira caso o nó ainda esteja inicializando.
                return
            self.processo.wait(timeout=30)

    def carteiras(self):
        return sorted(registro["name"] for registro in self.rpc("listwalletdir")["wallets"])

    def verificar_nova_carteira(self, nome):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,31}", nome):
            raise ErroNo("Use de 1 a 32 letras sem acento, números, hífens ou sublinhados.")
        if self.carteira is not None or nome in self.carteiras():
            raise ErroNo("Saia da carteira ativa e escolha um nome ainda não usado.")

    def abrir(self, nome, senha):
        self.verificar_senha(senha)
        self.conferir_genese()
        if self.carteira is not None or nome not in self.carteiras():
            raise ErroNo("Escolha uma carteira existente sem outra carteira ativa.")
        propria = nome not in self.rpc("listwallets")
        if propria:
            self.rpc("loadwallet", nome, False)
        self.carteira = nome
        try:
            self.rpc("verifyreal26passphrase", senha, carteira=True)
        except Exception:
            self.carteira = None
            if propria:
                try:
                    self.rpc("unloadwallet", nome, False)
                except (ErroNo, subprocess.TimeoutExpired):
                    pass  # A carteira continua indisponível na interface.
            raise
        self.carteira_propria = propria

    def sair(self):
        if self.carteira is not None and self.carteira_propria:
            self.rpc("unloadwallet", self.carteira, False)
        self.carteira = None
        self.carteira_propria = False

    def estado(self, limite_atividades=50):
        cadeia = self.rpc("getblockchaininfo")
        carteira = self.carteira in self.rpc("listwallets")
        dados = {"altura": cadeia["blocks"], "carteira": carteira, "nome": self.carteira if carteira else None}
        if self.compartilhado:
            pares = self.pares_conectados()
            dados["pares"] = len(pares)
            dados["sincronizando"] = cadeia["initialblockdownload"]
            dados["pode_minerar"] = self.rede_pronta_para_minerar(cadeia, pares)
        if carteira:
            info = self.rpc("getwalletinfo", carteira=True)
            if "unlocked_until" not in info:
                raise ErroNo("A interface requer uma carteira criptografada.")
            transacoes = self.rpc("listtransactions", "*", limite_atividades + 1, 0, carteira=True)
            dados.update(
                saldos=self.rpc("getbalances", carteira=True)["mine"],
                bloqueada=info["unlocked_until"] == 0,
                transacoes=transacoes[-limite_atividades:],
                mais_atividades=len(transacoes) > limite_atividades,
            )
        return dados

    def pares_conectados(self):
        return [par for par in self.rpc("getpeerinfo") if par["version"] > 0]

    @staticmethod
    def rede_pronta_para_minerar(cadeia, pares):
        if not pares or cadeia["blocks"] != cadeia["headers"]:
            return False
        if not cadeia["initialblockdownload"]:
            return True
        # A testnet sem blocos precisa produzir o primeiro antes de sair da sincronização inicial.
        return cadeia["blocks"] == 0 and all(
            max(par["synced_headers"], par["presynced_headers"]) <= 0 for par in pares
        )

    def conferir_mineracao(self):
        if self.compartilhado and not self.rede_pronta_para_minerar(
            self.rpc("getblockchaininfo"), self.pares_conectados()
        ):
            raise ErroNo("A mineração compartilhada exige conexão com um par e sincronização.")

    @staticmethod
    def verificar_senha(senha):
        if not senha or not senha.strip() or any(c in senha for c in "\r\n\x00"):
            raise ErroNo("Informe uma senha válida em uma única linha.")

    def criar(self, senha, nome=CARTEIRA):
        self.verificar_senha(senha)
        if len(senha.strip()) < MINIMO_SENHA_NOVA:
            raise ErroNo(f"Use pelo menos {MINIMO_SENHA_NOVA} caracteres na senha da nova carteira.")
        self.conferir_genese()
        self.verificar_nova_carteira(nome)
        self.rpc("createwallet", nome, False, False, senha)
        self.carteira = nome
        self.carteira_propria = True
        try:
            self.desbloquear(senha)
            endereco = self.receber()
        except Exception:
            self.bloquear_apos_falha()
            raise
        self.bloquear()
        return endereco

    def conferir_genese(self):
        if self.rpc("getblockhash", 0) != self.genese:
            self.carteira = None
            self.carteira_propria = False
            raise ErroNo("O gênese do nó difere do gênese do perfil selecionado.")

    def desbloquear(self, senha, segundos=30):
        self.verificar_senha(senha)
        self.conferir_genese()
        self.rpc("walletpassphrase", senha, segundos, carteira=True)

    def bloquear(self):
        self.rpc("walletlock", carteira=True)

    def bloquear_apos_falha(self):
        if self.carteira is not None:
            try:
                self.bloquear()
            except (ErroNo, subprocess.TimeoutExpired):
                pass  # O desbloqueio expira pelo prazo que o nó recebeu.

    def receber(self):
        return self.rpc("getreal26address", carteira=True)

    @staticmethod
    def quantia(valor):
        try:
            valor = Decimal(valor.strip().replace(",", "."))
            if not valor.is_finite() or not 0 < valor <= 21_000_000 or valor.quantize(CASA_DECIMAL) != valor:
                raise InvalidOperation
        except InvalidOperation as erro:
            raise ErroNo("Informe um valor positivo com até oito casas decimais.") from erro
        return format(valor, "f")

    def validar_destino(self, endereco):
        endereco = endereco.strip()
        destino = self.rpc("validateaddress", endereco)
        script = destino.get("scriptPubKey", "")
        if not (
            destino["isvalid"]
            and endereco.startswith(self.prefixo_destino)
            and destino.get("address") == endereco
            and script.startswith("5220")
            and len(script) == 68
        ):
            raise ErroNo("Informe um endereço ML-DSA-65 válido da rede selecionada.")
        return endereco

    def estimar_taxa(self, endereco, valor):
        self.validar_destino(endereco)
        valor = Decimal(self.quantia(valor))
        politica = self.rpc("getmempoolinfo")
        estimativa = self.rpc("estimatesmartfee", 2).get("feerate", 0)
        taxa_por_kvb = max(politica["mempoolminfee"], estimativa)
        bloqueadas = {(c["txid"], c["vout"]) for c in self.rpc("listlockunspent", carteira=True)}
        moedas = self.rpc("listunspent", 1, 9999999, [self.receber()], True, carteira=True)
        valores = sorted(
            (c["amount"] for c in moedas if c["spendable"] and (c["txid"], c["vout"]) not in bloqueadas),
            reverse=True,
        )
        total = Decimal(0)
        for entradas, saldo in enumerate(valores, 1):
            total += saldo
            # Uma saída para o destinatário e outra reservada para o troco.
            base = 10 + 41 * entradas + 2 * 43
            peso_base = 4 * base + 2
            # O RPC de envio verifica o limite antes de compactar as chaves.
            if peso_base + entradas * 5268 > 400_000:
                raise ErroNo("O pagamento excede o peso padrão de uma transação.")
            # A primeira entrada leva a chave completa; as demais levam uma referência de um byte.
            peso = peso_base + 5268 + (entradas - 1) * 3315
            tamanho_virtual = (peso + 3) // 4
            taxa = max(
                CASA_DECIMAL,
                (taxa_por_kvb * tamanho_virtual / 1000).quantize(CASA_DECIMAL, rounding=ROUND_CEILING),
            )
            if total >= valor + taxa:
                return format(taxa, "f")
        raise ErroNo("Saldo confirmado e maduro insuficiente para o valor e a taxa.")

    def enviar(self, endereco, valor, taxa, senha):
        self.verificar_senha(senha)
        self.conferir_genese()
        endereco = self.validar_destino(endereco)
        valor, taxa = self.quantia(valor), self.quantia(taxa)
        try:
            txid = self.rpc("sendreal26", endereco, valor, taxa, senha, carteira=True)
        except subprocess.TimeoutExpired as erro:
            raise ErroNo(
                "O estado do envio ficou incerto. Confira a Atividade antes de tentar novamente."
            ) from erro
        return txid, ""

    def caminho_windows(self, caminho):
        if self.nativo:
            return str(Path(caminho).absolute())
        return self.executar(("wslpath", "-a", "-u", caminho.replace(chr(92), "/")))

    def backup(self, caminho):
        self.conferir_genese()
        if "unlocked_until" not in self.rpc("getwalletinfo", carteira=True):
            raise ErroNo("A interface só gera backups de carteiras criptografadas.")
        destino = Path(caminho).absolute()
        if destino.exists() or destino.is_symlink():
            raise ErroNo("Já existe um arquivo nesse local. Escolha outro nome para o backup.")
        # Grave e valide na mesma unidade. No Windows, rename recusa um destino existente.
        with TemporaryDirectory(prefix=".real26-backup-", dir=destino.parent) as pasta:
            arquivo = Path(pasta) / "carteira.dat"
            self.rpc("backupwallet", self.caminho_windows(str(arquivo)), carteira=True)
            banco = sqlite3.connect(arquivo.as_uri() + "?mode=ro&immutable=1", uri=True)
            try:
                if banco.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise ErroNo("O arquivo de backup falhou na verificação de integridade.")
            finally:
                banco.close()
            try:
                arquivo.rename(destino)
            except FileExistsError as erro:
                raise ErroNo("Já existe um arquivo nesse local. Escolha outro nome para o backup.") from erro

    def restaurar(self, caminho, nome=CARTEIRA):
        self.conferir_genese()
        self.verificar_nova_carteira(nome)
        self.rpc("restorewallet", nome, self.caminho_windows(caminho), False)
        self.rpc("unloadwallet", nome, False)
