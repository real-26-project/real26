# Distribuído sob a licença MIT. Consulte COPYING.
"""Carteira desktop REAL-26 para a rede privada de ensaio."""

from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor
import ctypes as c
from decimal import Decimal
from os import process_cpu_count
from pathlib import Path
from queue import Empty
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, simpledialog, ttk

from idiomas import IDIOMAS, carregar_idioma, salvar_idioma, traducao
from mineracao import Minerador
from no_real26 import ErroNo, MINIMO_SENHA_NOVA, NoReal26, SenhaIncorreta


FUNDO = "#0B1422"
MARINHO = "#123055"
ITENS_HISTORICO = 50
LATERAL = "#101E33"
PAINEL = "#15243A"
BORDA = "#2C4360"
TEXTO = "#F4F7FC"
SUAVE = "#B5C6DB"
DOURADO = "#FFD16D"
VERDE = "#78E2B0"
ERRO = "#FFADA9"
BOTAO = "#213855"
HOVER = "#315174"
FONTE = "Segoe UI"
ARTES = Path(__file__).resolve().parent


def moedas(valor):
    inteiro, fracao = f"{Decimal(valor):,.8f}".split(".")
    return inteiro.replace(",", ".") + "," + fracao


class Dialogo(simpledialog.Dialog):
    def __init__(self, pai, titulo, traduzir):
        self.t = traduzir
        super().__init__(pai, titulo)

    def buttonbox(self):
        acoes = ttk.Frame(self)
        ttk.Button(acoes, text="OK", command=self.ok).pack(side="left", padx=5, pady=5)
        ttk.Button(acoes, text=self.t("Cancelar"), command=self.cancel).pack(side="left", padx=5, pady=5)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        acoes.pack()


class Entrada(Dialogo):
    def __init__(self, pai, titulo, mensagem, traduzir, oculto=False):
        self.mensagem = mensagem
        self.oculto = oculto
        super().__init__(pai, titulo, traduzir)

    def body(self, quadro):
        ttk.Label(quadro, text=self.mensagem, wraplength=380).pack(anchor="w", padx=12, pady=(12, 6))
        self.campo = ttk.Entry(quadro, width=40, show="●" if self.oculto else "")
        self.campo.pack(fill="x", padx=12, pady=(0, 8))
        return self.campo

    def apply(self):
        self.result = self.campo.get()


class SeletorCarteira(Dialogo):
    def __init__(self, pai, nomes, traduzir):
        self.nomes = nomes
        super().__init__(pai, traduzir("Abrir carteira"), traduzir)

    def body(self, quadro):
        self.seletor = ttk.Combobox(quadro, values=self.nomes, state="readonly", width=32)
        self.seletor.current(0)
        self.seletor.pack(padx=12, pady=12)
        return self.seletor

    def apply(self):
        self.result = self.seletor.get()


class Carteira:
    def __init__(self, janela, no):
        self.janela, self.no = janela, no
        self.compartilhado = getattr(no, "compartilhado", False)
        self.idioma = carregar_idioma()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.tarefa = None
        self.tarefa_silenciosa = False
        self.dados = {}
        self.ultima_atividade = None
        self.limite_atividades = ITENS_HISTORICO
        self.minerador = Minerador(no)
        self.estado_minerador = "parado"
        self.dispositivo = None
        self.limite_cpu = min(process_cpu_count() or 1, 61)
        titulo = self.t("REAL-26 | Carteira nativa") if no.nativo else self.t("REAL-26 | Carteira")
        if self.compartilhado:
            titulo = f"REAL-26 | {self.t('Teste compartilhado')}"
        janela.title(titulo)
        janela.iconbitmap(default=str(ARTES / "real26.ico"))
        janela.configure(bg=FUNDO)
        janela.geometry("1120x730")
        janela.minsize(970, 640)
        janela.protocol("WM_DELETE_WINDOW", self.fechar)
        self.montar()
        janela.bind("<Map>", self.ao_exibir_janela, add="+")
        janela.after(100, self.colorir_titulo)
        self.operacao(self.iniciar, self.atualizar)
        janela.after(12000, self.atualizacao_periodica)
        janela.after(150, self.ler_minerador)

    def t(self, texto, *valores):
        return traducao(self.idioma, texto, *valores)

    def moedas(self, valor):
        return f"{Decimal(valor):,.8f}" if self.idioma == "en" else moedas(valor)

    def pedir(self, titulo, mensagem, *, show=None):
        return Entrada(self.janela, titulo, mensagem, self.t, oculto=show is not None).result

    def alterar_idioma(self, _):
        codigo = tuple(IDIOMAS)[self.seletor_idioma.current()]
        try:
            salvar_idioma(codigo)
        except OSError as erro:
            self.seletor_idioma.set(IDIOMAS[self.idioma])
            self.aviso(self.t("Falha ao salvar idioma"), str(erro), cor=ERRO)
        else:
            if codigo == self.idioma:
                return
            self.aviso(
                traducao(codigo, "Alterar idioma"),
                traducao(codigo, "Idioma salvo. Feche e reabra a carteira para aplicar."),
            )

    def abrir_teste_compartilhado(self):
        self.abrir_perfil(compartilhado=True)

    def adicionar_par(self):
        par = self.pedir(self.t("Adicionar nó"), self.t("Endereço do nó (host:porta)"))
        if not par:
            return

        def adicionar():
            self.no.adicionar_par(par)
            return self.ler_estado()

        self.operacao(
            adicionar, self.atualizar, lambda _, erro: self.aviso(self.t("Adicionar nó"), erro, cor=ERRO)
        )

    def abrir_perfil(self, *, compartilhado=False):
        try:
            subprocess.Popen(
                (
                    sys.executable,
                    "-E",
                    "-s",
                    "-B",
                    str(Path(__file__).resolve()),
                    "--binarios",
                    str(Path(self.no.cli).parent),
                    *(("--testnet",) if compartilhado else ()),
                ),
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except OSError as erro:
            self.aviso(self.t("Falha ao abrir o perfil de teste"), str(erro), cor=ERRO)

    def ao_exibir_janela(self, evento):
        if evento.widget is self.janela:
            self.janela.after_idle(self.colorir_titulo)

    def colorir_titulo(self, janela=None):
        janela = self.janela if janela is None else janela
        user32 = c.windll.user32
        user32.GetAncestor.argtypes = [c.c_void_p, c.c_uint]
        user32.GetAncestor.restype = c.c_void_p
        hwnd = user32.GetAncestor(janela.winfo_id(), 2)
        definir = c.windll.dwmapi.DwmSetWindowAttribute
        definir.argtypes = [c.c_void_p, c.c_uint, c.c_void_p, c.c_uint]
        definir.restype = c.c_long
        # A barra nativa mantém as funções normais de redimensionamento e arraste.
        for atributo, cor in ((35, MARINHO), (36, TEXTO)):
            r, g, b = bytes.fromhex(cor[1:])
            rgb = c.c_uint(r | g << 8 | b << 16)
            definir(hwnd, atributo, c.byref(rgb), c.sizeof(rgb))
        redesenhar = user32.RedrawWindow
        redesenhar.argtypes = [c.c_void_p, c.c_void_p, c.c_void_p, c.c_uint]
        redesenhar(hwnd, None, None, 0x0401)

    def fechar(self):
        self.minerador.encerrar()
        if self.no.nativo:
            self.executor.submit(self.encerrar_no_nativo)
        self.executor.shutdown(wait=False, cancel_futures=not self.no.nativo)
        self.janela.destroy()

    def encerrar_no_nativo(self):
        if self.minerador.thread is not None:
            self.minerador.thread.join(timeout=10)
        self.no.encerrar_no_proprio()

    def texto(self, pai, texto, *, fundo=PAINEL, cor=TEXTO, tamanho=11, peso="normal", **kw):
        return tk.Label(pai, text=texto, bg=fundo, fg=cor, font=(FONTE, tamanho, peso), **kw)

    def botao(self, pai, titulo, acao, destaque=False):
        return tk.Button(
            pai,
            text=titulo,
            command=acao,
            anchor="center",
            relief="flat",
            overrelief="flat",
            bd=0,
            padx=13,
            pady=8,
            bg=DOURADO if destaque else BOTAO,
            fg=FUNDO if destaque else TEXTO,
            activebackground="#FFE4A1" if destaque else HOVER,
            activeforeground=FUNDO if destaque else TEXTO,
            disabledforeground="#8298B2",
            cursor="hand2",
            font=(FONTE, 10, "bold"),
            highlightthickness=1,
            highlightbackground=pai.cget("bg"),
            highlightcolor=DOURADO,
        )

    def aviso(self, titulo, mensagem, *, pai=None, cor=DOURADO, confirmar=None):
        pai = self.janela if pai is None else pai
        anterior = pai.grab_current()
        foco = pai.focus_get()
        janela = tk.Toplevel(pai)
        janela.withdraw()
        janela.title(f"REAL-26 | {titulo}")
        janela.transient(pai)
        janela.configure(bg=PAINEL)
        janela.resizable(False, False)
        aceito = False

        def fechar(resultado=False):
            nonlocal aceito
            aceito = resultado
            janela.destroy()

        tk.Frame(janela, bg=cor, height=3).pack(fill="x")
        self.texto(janela, titulo, cor=cor, tamanho=19, peso="bold").pack(anchor="w", padx=24, pady=(18, 8))
        self.texto(janela, mensagem, justify="left", wraplength=420).pack(anchor="w", padx=24)
        acoes = tk.Frame(janela, bg=PAINEL)
        acoes.pack(fill="x", padx=24, pady=20)
        principal = self.botao(acoes, confirmar or "OK", lambda: fechar(True), True)
        principal.pack(side="right")
        foco_inicial = principal
        if confirmar:
            foco_inicial = self.botao(acoes, self.t("Cancelar"), fechar)
            foco_inicial.pack(side="right", padx=(0, 8))
        janela.protocol("WM_DELETE_WINDOW", fechar)
        janela.bind("<Escape>", lambda _: fechar())
        janela.bind("<Return>", lambda _: fechar(janela.focus_get() is principal))
        janela.update_idletasks()
        x = pai.winfo_rootx() + (pai.winfo_width() - janela.winfo_reqwidth()) // 2
        y = pai.winfo_rooty() + (pai.winfo_height() - janela.winfo_reqheight()) // 2
        janela.geometry(f"+{max(0, x)}+{max(0, y)}")
        janela.deiconify()
        janela.wait_visibility()
        self.colorir_titulo(janela)
        janela.grab_set()
        foco_inicial.focus_set()
        pai.wait_window(janela)
        if anterior is not None and anterior.winfo_exists():
            anterior.grab_set()
        if foco is not None and foco.winfo_exists():
            foco.focus_set()
        return aceito

    def montar(self):
        lateral = tk.Frame(self.janela, bg=LATERAL, width=222, highlightbackground=BORDA, highlightthickness=1)
        lateral.pack(side="left", fill="y")
        lateral.pack_propagate(False)
        cabecalho_lateral = tk.Frame(lateral, bg=LATERAL)
        cabecalho_lateral.pack(fill="x", pady=(0, 12))
        margem, espaco_titulo = 18, 10
        logo = tk.Frame(cabecalho_lateral, bg=LATERAL)
        logo.pack(fill="x", padx=margem, pady=(25, 10))
        self.medalhao = tk.PhotoImage(file=str(ARTES / "real26-carteira.png"))
        simbolo = tk.Label(logo, image=self.medalhao, bg=LATERAL, bd=0)
        simbolo.pack(side="left")
        titulo = self.texto(logo, "REAL-26", fundo=LATERAL, tamanho=18, peso="bold")
        titulo.pack(side="left", padx=(espaco_titulo, 0))
        largura_logo = simbolo.winfo_reqwidth() + titulo.winfo_reqwidth() + espaco_titulo + 2 * margem
        lateral.configure(width=max(222, largura_logo + 2 * int(lateral.cget("highlightthickness"))))
        self.texto(cabecalho_lateral, self.t("CARTEIRA"), fundo=LATERAL, cor=SUAVE, tamanho=9, peso="bold").pack(
            anchor="w", padx=24, pady=(0, 19)
        )
        self.botoes = {}
        for nome, titulo, comando in (
            ("criar", self.t("Criar carteira"), self.criar),
            ("abrir", self.t("Abrir carteira"), self.abrir),
            ("receber", self.t("Receber"), self.receber),
            ("enviar", self.t("Enviar"), self.enviar),
            ("backup", self.t("Fazer backup"), self.backup),
            ("restaurar", self.t("Restaurar backup"), self.restaurar),
            ("sair", self.t("Sair da carteira"), self.sair),
        ):
            b = self.botao(lateral, titulo, comando)
            b.config(anchor="w")
            b.pack(fill="x", padx=18, pady=(6, 0))
            self.botoes[nome] = b
        if self.no.nativo:
            titulo = "Teste isolado" if self.compartilhado else "Conectar à testnet"
            alternar = self.abrir_perfil if self.compartilhado else self.abrir_teste_compartilhado
            self.botao(lateral, self.t(titulo), alternar, destaque=not self.compartilhado).pack(
                fill="x", padx=18, pady=(10, 0)
            )
            if self.compartilhado:
                self.botoes["adicionar_par"] = self.botao(lateral, self.t("Adicionar nó"), self.adicionar_par)
                self.botoes["adicionar_par"].pack(fill="x", padx=18, pady=(6, 0))
        painel_idioma = tk.Frame(lateral, bg=LATERAL)
        painel_idioma.pack(side="bottom", fill="x", padx=20, pady=(0, 13))
        self.texto(painel_idioma, self.t("Idioma"), fundo=LATERAL, cor=SUAVE, tamanho=10).pack(anchor="w")
        self.seletor_idioma = ttk.Combobox(painel_idioma, state="readonly", values=tuple(IDIOMAS.values()))
        self.seletor_idioma.set(IDIOMAS[self.idioma])
        self.seletor_idioma.pack(fill="x", pady=(4, 0))
        self.seletor_idioma.bind("<<ComboboxSelected>>", self.alterar_idioma)

        area = tk.Frame(self.janela, bg=FUNDO)
        area.pack(side="left", fill="both", expand=True, padx=34, pady=28)
        topo = tk.Frame(area, bg=FUNDO)
        topo.pack(fill="x")
        self.texto(topo, self.t("Visão geral"), fundo=FUNDO, tamanho=28, peso="bold").pack(side="left")
        self.estado_no = self.texto(
            topo, self.t("Conectando ao nó"), fundo=MARINHO, cor=VERDE, tamanho=10, peso="bold", padx=10, pady=5
        )
        self.estado_no.pack(side="right", pady=8)

        saldo = tk.Frame(area, bg=PAINEL, highlightbackground=BORDA, highlightthickness=1)
        saldo.pack(fill="x", pady=(21, 14))
        faixa_rede = tk.Frame(saldo, bg=MARINHO)
        faixa_rede.pack(fill="x")
        rede_ativa = "Teste compartilhado · ASERT" if self.compartilhado else "Teste isolado · Ativo"
        self.texto(faixa_rede, self.t(rede_ativa), fundo=MARINHO, cor=DOURADO, tamanho=10, peso="bold").pack(
            side="left", padx=(22, 10), pady=7
        )
        self.texto(
            faixa_rede,
            self.t("Moedas de teste sem valor. A rede pode ser reiniciada."),
            fundo=MARINHO,
            cor=TEXTO,
            tamanho=10,
        ).pack(side="left", pady=7)
        alto = tk.Frame(saldo, bg=PAINEL)
        alto.pack(fill="x", padx=22, pady=(17, 0))
        self.texto(alto, self.t("SALDO DISPONÍVEL"), cor=DOURADO, tamanho=10, peso="bold").pack(side="left")
        self.seguranca = self.texto(alto, "", cor=SUAVE, tamanho=10)
        self.seguranca.pack(side="right")
        self.saldo = self.texto(saldo, "—", tamanho=35, peso="bold")
        self.saldo.pack(anchor="w", padx=22, pady=(3, 7))
        baixo = tk.Frame(saldo, bg=PAINEL)
        baixo.pack(fill="x", padx=22, pady=(0, 16))
        self.pendente = self.texto(baixo, self.t("Aguardando confirmação") + "  —", cor=SUAVE, tamanho=10)
        self.pendente.pack(side="left")
        self.imaturo = self.texto(baixo, self.t("Recompensas a amadurecer") + "  —", cor=SUAVE, tamanho=10)
        self.imaturo.pack(side="right")

        mineracao = tk.Frame(area, bg=PAINEL, highlightbackground=BORDA, highlightthickness=1)
        mineracao.pack(fill="x", pady=(0, 14))
        linha_mineracao = tk.Frame(mineracao, bg=PAINEL)
        linha_mineracao.pack(fill="x")
        info_mineracao = tk.Frame(linha_mineracao, bg=PAINEL)
        info_mineracao.pack(side="left", padx=18, pady=10)
        self.texto(info_mineracao, self.t("Mineração"), tamanho=15, peso="bold").pack(anchor="w")
        self.status_mineracao = self.texto(info_mineracao, self.t("Parada"), cor=SUAVE, tamanho=10)
        self.status_mineracao.pack(anchor="w")
        self.taxa_mineracao = self.texto(linha_mineracao, "— MH/s", cor=DOURADO, tamanho=13, peso="bold")
        self.taxa_mineracao.pack(side="left", padx=(10, 0))
        self.blocos_minerados = self.texto(linha_mineracao, self.t("{0} blocos", 0), cor=SUAVE, tamanho=10)
        self.blocos_minerados.pack(side="left", padx=12)
        self.botao_encerrar = self.botao(linha_mineracao, self.t("Encerrar"), self.encerrar_mineracao)
        self.botao_encerrar.pack(side="right", padx=(6, 14))
        self.botao_minerar = self.botao(linha_mineracao, self.t("Iniciar"), self.alternar_mineracao, destaque=True)
        self.botao_minerar.pack(side="right")
        opcoes = tk.Frame(mineracao, bg=PAINEL)
        opcoes.pack(fill="x", padx=18, pady=(0, 10))
        self.texto(opcoes, self.t("Modo"), cor=SUAVE, tamanho=10).pack(side="left")
        self.modo_mineracao = ttk.Combobox(
            opcoes, state="readonly", width=14, values=(self.t("Automático"), "CPU", "GPU")
        )
        self.modo_mineracao.current(0)
        self.modo_mineracao.pack(side="left", padx=(7, 14))
        self.modo_mineracao.bind("<<ComboboxSelected>>", lambda _: self.habilitar())
        self.texto(opcoes, self.t("Threads de CPU"), cor=SUAVE, tamanho=10).pack(side="left")
        self.threads_cpu = ttk.Spinbox(opcoes, from_=1, to=self.limite_cpu, width=4)
        self.threads_cpu.set("1")
        self.threads_cpu.pack(side="left", padx=(7, 0))

        quadro = tk.Frame(area, bg=PAINEL, highlightbackground=BORDA, highlightthickness=1)
        quadro.pack(fill="both", expand=True)
        cab = tk.Frame(quadro, bg=PAINEL)
        cab.pack(fill="x", padx=18, pady=13)
        self.texto(cab, self.t("Atividade"), tamanho=17, peso="bold").pack(side="left")
        self.botao(cab, self.t("Atualizar"), lambda: self.operacao(self.iniciar, self.atualizar)).pack(
            side="right"
        )
        estilo = ttk.Style(self.janela)
        estilo.theme_use("clam")
        for controle in ("TCombobox", "TSpinbox"):
            estilo.configure(
                controle,
                fieldbackground=FUNDO,
                background=BOTAO,
                foreground=TEXTO,
                arrowcolor=DOURADO,
                bordercolor=BORDA,
                lightcolor=BORDA,
                darkcolor=BORDA,
                padding=4,
            )
            estilo.map(
                controle,
                fieldbackground=[("readonly", FUNDO)],
                foreground=[("disabled", SUAVE), ("readonly", TEXTO)],
                bordercolor=[("focus", DOURADO)],
            )
        self.janela.option_add("*TCombobox*Listbox.background", PAINEL)
        self.janela.option_add("*TCombobox*Listbox.foreground", TEXTO)
        self.janela.option_add("*TCombobox*Listbox.selectBackground", HOVER)
        estilo.configure(
            "Real26.Treeview",
            background=PAINEL,
            fieldbackground=PAINEL,
            foreground=TEXTO,
            borderwidth=0,
            rowheight=30,
            font=(FONTE, 10),
        )
        estilo.configure("Real26.Treeview.Heading", background=BORDA, foreground=TEXTO, relief="flat", padding=7)
        estilo.map("Real26.Treeview", background=[("selected", HOVER)])
        lista = tk.Frame(quadro, bg=PAINEL)
        lista.pack(fill="both", expand=True, padx=18)
        estilo.configure(
            "Real26.Vertical.TScrollbar", background=BORDA, troughcolor=FUNDO, bordercolor=PAINEL, arrowcolor=TEXTO
        )
        rolagem = ttk.Scrollbar(lista, orient="vertical", style="Real26.Vertical.TScrollbar")
        rolagem.pack(side="right", fill="y")
        self.tabela = ttk.Treeview(
            lista,
            columns=("tipo", "valor", "confirmacoes", "tx"),
            show="headings",
            style="Real26.Treeview",
            height=5,
            yscrollcommand=rolagem.set,
        )
        self.tabela.tag_configure("linha_alternada", background="#1A2C45")
        rolagem.config(command=self.tabela.yview)
        for coluna, titulo, largura in (
            ("tipo", self.t("Operação"), 112),
            ("valor", self.t("Valor (REAL-26)"), 142),
            ("confirmacoes", self.t("Confirmações"), 100),
            ("tx", self.t("Identificador"), 205),
        ):
            self.tabela.heading(coluna, text=titulo, anchor="w")
            self.tabela.column(coluna, width=largura, minwidth=80)
        self.tabela.pack(side="left", fill="both", expand=True)
        self.tabela.bind("<Double-1>", self.copiar_transacao)
        rodape = tk.Frame(quadro, bg=PAINEL)
        rodape.pack(before=lista, side="bottom", fill="x", padx=18, pady=10)
        self.estado = self.texto(rodape, self.t("Conectando ao nó"), cor=SUAVE, tamanho=10)
        self.botao_anteriores = self.botao(rodape, self.t("Carregar anteriores"), self.carregar_anteriores)
        self.botao_anteriores.pack(side="right")
        self.estado.pack(side="left", anchor="w")
        self.habilitar()

    def habilitar(self):
        def definir(botao, disponivel):
            if (str(botao.cget("state")) != "disabled") != bool(disponivel):
                botao.config(state="normal" if disponivel else "disabled")

        existe = self.dados.get("carteira", False)
        livre = self.tarefa is None or self.tarefa_silenciosa
        for nome, botao in self.botoes.items():
            disponivel = (
                self.dados and livre and (not existe if nome in ("criar", "abrir", "restaurar") else existe)
            )
            if nome == "adicionar_par":
                disponivel = self.dados and livre
            if nome == "sair":
                disponivel = disponivel and self.estado_minerador == "parado"
            definir(botao, disponivel)
        rede_pronta = not self.compartilhado or self.dados.get("pode_minerar")
        pode_minerar = (
            existe
            and livre
            and (
                self.estado_minerador == "minerando"
                or (rede_pronta and self.estado_minerador in ("parado", "pausado"))
            )
        )
        definir(self.botao_minerar, pode_minerar)
        fundo_minerar = DOURADO if pode_minerar else BOTAO
        if self.botao_minerar.cget("bg") != fundo_minerar:
            self.botao_minerar.config(bg=fundo_minerar)
        definir(self.botao_encerrar, self.estado_minerador in ("iniciando", "minerando", "pausado"))
        definir(self.botao_anteriores, livre and self.dados.get("mais_atividades"))
        parado = self.estado_minerador == "parado"
        estado_seletor = "readonly" if parado else "disabled"
        if str(self.modo_mineracao.cget("state")) != estado_seletor:
            self.modo_mineracao.configure(state=estado_seletor)
        definir(self.threads_cpu, parado and self.modo_mineracao.current() != 2)

    def ler_estado(self):
        return self.no.estado(self.limite_atividades)

    def carregar_anteriores(self):
        if (self.tarefa is None or self.tarefa_silenciosa) and self.dados.get("mais_atividades"):
            self.limite_atividades += ITENS_HISTORICO
            self.operacao(self.ler_estado, self.atualizar)

    def alternar_mineracao(self):
        if self.estado_minerador == "parado":
            modo = ("auto", "cpu", "gpu")[self.modo_mineracao.current()]
            try:
                trabalhadores = 1 if modo == "gpu" else int(self.threads_cpu.get())
                if not 1 <= trabalhadores <= self.limite_cpu:
                    raise ValueError
            except ValueError:
                self.aviso(
                    self.t("Threads de CPU"),
                    self.t("Escolha de 1 a {0} threads de CPU.", self.limite_cpu),
                    cor=ERRO,
                )
                return
            if not self.minerador.iniciar(modo, trabalhadores):
                return
            self.estado_minerador = "iniciando"
            self.status_mineracao.config(text=self.t("Preparando mineração…"), fg=SUAVE)
            self.taxa_mineracao.config(text="— MH/s")
            self.blocos_minerados.config(text=self.t("{0} blocos", 0))
        elif self.estado_minerador == "minerando":
            self.minerador.pausar()
            self.estado_minerador = "pausado"
            self.status_mineracao.config(text=self.t("Pausada"), fg=SUAVE)
            self.botao_minerar.config(text=self.t("Retomar"))
        elif self.estado_minerador == "pausado":
            self.minerador.retomar()
            self.estado_minerador = "minerando"
            self.status_mineracao.config(text=self.t("Minerando · {0}", self.dispositivo), fg=VERDE)
            self.botao_minerar.config(text=self.t("Pausar"))
        self.habilitar()

    def encerrar_mineracao(self):
        self.minerador.encerrar()
        self.estado_minerador = "encerrando"
        self.status_mineracao.config(text=self.t("Encerrando…"), fg=SUAVE)
        self.habilitar()

    def ler_minerador(self):
        while True:
            try:
                evento, valor = self.minerador.eventos.get_nowait()
            except Empty:
                break
            if evento == "minerando" and self.estado_minerador == "iniciando":
                self.estado_minerador = "minerando"
                self.dispositivo = valor
                self.status_mineracao.config(text=self.t("Minerando · {0}", valor), fg=VERDE)
                self.botao_minerar.config(text=self.t("Pausar"))
            elif evento == "alternativa" and self.estado_minerador == "iniciando":
                self.status_mineracao.config(text=self.t("GPU indisponível. Preparando a CPU…"), fg=SUAVE)
            elif evento == "taxa" and self.estado_minerador == "minerando":
                taxa = f"{valor:.1f}"
                self.taxa_mineracao.config(
                    text=(taxa if self.idioma == "en" else taxa.replace(".", ",")) + " MH/s"
                )
            elif evento == "bloco":
                total, altura = valor
                self.blocos_minerados.config(
                    text=self.t("{0} bloco", total) if total == 1 else self.t("{0} blocos", total)
                )
                if self.janela.grab_current() is None:
                    self.operacao(self.ler_estado, self.atualizar, silenciosa=True)
            elif evento == "erro":
                self.status_mineracao.config(text=self.t("Falha na mineração"), fg=ERRO)
                self.aviso(self.t("Falha na mineração"), self.t(valor), cor=ERRO)
            elif evento == "encerrado":
                self.estado_minerador = "parado"
                self.status_mineracao.config(text=self.t("Parada"), fg=SUAVE)
                self.botao_minerar.config(text=self.t("Iniciar"))
                self.taxa_mineracao.config(text="— MH/s")
            self.habilitar()
        self.janela.after(150, self.ler_minerador)

    def iniciar(self):
        self.no.conectar()
        return self.ler_estado()

    def operacao(self, trabalho, sucesso, falha=None, *, silenciosa=False):
        if self.tarefa is not None and (silenciosa or not self.tarefa_silenciosa):
            return
        if not silenciosa:
            self.estado.config(text=self.t("Consultando o nó local…"))
        tarefa = self.tarefa = self.executor.submit(trabalho)
        self.tarefa_silenciosa = silenciosa
        self.habilitar()
        self.janela.after(80, lambda: self.concluir(tarefa, sucesso, falha))

    def concluir(self, tarefa, sucesso, falha):
        if tarefa is not self.tarefa:
            return
        if not tarefa.done():
            self.janela.after(80, lambda: self.concluir(tarefa, sucesso, falha))
            return
        self.tarefa = None
        self.tarefa_silenciosa = False
        try:
            resultado = tarefa.result()
        except Exception as erro:
            mensagem = self.t(str(erro).strip() or "A operação falhou.")
            self.estado.config(text=self.t(mensagem.splitlines()[-1])[:150], fg=ERRO)
            if falha is None:
                self.estado_no.config(text=self.t("Verifique o nó local"), fg=ERRO)
            else:
                falha(erro, mensagem)
        else:
            self.estado.config(fg=SUAVE)
            sucesso(resultado)
        self.habilitar()

    def atualizar(self, dados):
        if dados["nome"] != self.dados.get("nome"):
            self.ultima_atividade = None
            self.limite_atividades = ITENS_HISTORICO
        self.dados = dados
        if self.compartilhado:
            status = "Sincronizando  ·  Pares: {1}" if dados["sincronizando"] else "Bloco {0}  ·  Pares: {1}"
            if dados["sincronizando"] and dados["pode_minerar"]:
                status = "Aguardando primeiro bloco  ·  Pares: {1}"
            self.estado_no.config(
                text=self.t(status, dados["altura"], dados["pares"]),
                fg=VERDE if dados["pode_minerar"] else DOURADO,
            )
        else:
            self.estado_no.config(text=self.t("Nó local conectado  ·  Bloco {0}", dados["altura"]), fg=VERDE)
        saldos = dados.get("saldos")
        self.saldo.config(text="—" if saldos is None else f"{self.moedas(saldos['trusted'])}  REAL-26")
        if saldos is not None:
            estado = self.t("bloqueada") if dados["bloqueada"] else self.t("desbloqueada")
            self.seguranca.config(text=f"{dados['nome']}  ·  {estado}")
            self.pendente.config(
                text=self.t("Aguardando confirmação") + "  " + self.moedas(saldos["untrusted_pending"])
            )
            self.imaturo.config(text=self.t("Recompensas a amadurecer") + "  " + self.moedas(saldos["immature"]))
        else:
            self.seguranca.config(text=self.t("Nenhuma carteira aberta"))
            self.pendente.config(text=self.t("Aguardando confirmação") + "  —")
            self.imaturo.config(text=self.t("Recompensas a amadurecer") + "  —")
        # O RPC retorna o recorte do histórico em ordem crescente.
        transacoes = dados.get("transacoes", [])
        ultima = transacoes[-1]["txid"] if transacoes else None
        itens = self.tabela.get_children()
        linha_visivel = round(self.tabela.yview()[0] * len(itens)) if ultima == self.ultima_atividade else 0
        self.ultima_atividade = ultima
        if itens:
            self.tabela.delete(*itens)
        nomes = {
            "send": self.t("Enviado"),
            "receive": self.t("Recebido"),
            "generate": self.t("Minerado"),
            "immature": self.t("Recompensa"),
            "orphan": self.t("Bloco órfão"),
        }
        for indice, tx in enumerate(reversed(transacoes)):
            txid = tx["txid"]
            iid = self.tabela.insert(
                "",
                "end",
                values=(
                    nomes.get(tx["category"], tx["category"]),
                    self.moedas(tx["amount"]),
                    tx["confirmations"],
                    txid[:21] + "…",
                ),
            )
            tags = (txid, "linha_alternada") if indice % 2 else (txid,)
            self.tabela.item(iid, tags=tags)
        self.tabela.yview_moveto(linha_visivel / max(1, len(transacoes)))
        self.estado.config(
            text=(
                self.t("Abra uma carteira, crie outra ou restaure um backup.")
                if saldos is None
                else self.t("{0} atividades  ·  Clique duplo para copiar o ID.", len(transacoes))
                if transacoes
                else self.t("Nenhuma transação nesta carteira.")
            )
        )

    def atualizacao_periodica(self):
        if self.janela.grab_current() is None:
            self.operacao(self.iniciar, self.atualizar, silenciosa=True)
        self.janela.after(12000, self.atualizacao_periodica)

    def copiar(self, valor):
        self.janela.clipboard_clear()
        self.janela.clipboard_append(valor)

    def copiar_transacao(self, _):
        if selecionadas := self.tabela.selection():
            self.copiar(self.tabela.item(selecionadas[0], "tags")[0])
            self.estado.config(text=self.t("Identificador copiado."))

    def criar(self):
        nome = self.pedir(self.t("Criar carteira"), self.t("Nome da nova carteira"))
        if not nome:
            return
        senha = self.pedir(
            self.t("Criar carteira"),
            self.t("Senha da nova carteira (mínimo de {0} caracteres)", MINIMO_SENHA_NOVA),
            show="●",
        )
        if not senha:
            return
        if len(senha.strip()) < MINIMO_SENHA_NOVA:
            self.aviso(
                self.t("Senha muito curta"),
                self.t(
                    "Use pelo menos {0} caracteres. Uma frase longa e exclusiva é mais fácil de guardar.",
                    MINIMO_SENHA_NOVA,
                ),
                cor=ERRO,
            )
            return
        confirmacao = self.pedir(self.t("Criar carteira"), self.t("Repita a senha"), show="●")
        if senha != confirmacao:
            self.aviso(self.t("Senhas diferentes"), self.t("As senhas precisam coincidir."), cor=ERRO)
            return

        def criar():
            endereco = self.no.criar(senha, nome.strip())
            return self.ler_estado(), endereco

        def criada(resultado):
            dados, endereco = resultado
            self.atualizar(dados)
            self.exibir_endereco(endereco)

        self.operacao(criar, criada)

    def abrir(self):
        def escolher(nomes):
            if not nomes:
                self.estado.config(text=self.t("Nenhuma carteira encontrada. Crie uma ou restaure um backup."))
                return
            nome = SeletorCarteira(self.janela, nomes, self.t).result
            if nome is not None:
                self.pedir_senha_para_abrir(nome)

        self.operacao(self.no.carteiras, escolher)

    def pedir_senha_para_abrir(self, nome):
        senha = self.pedir(self.t("Abrir carteira"), self.t("Senha da carteira {0}", nome), show="●")
        if senha is None:
            return

        def falha(erro, mensagem):
            titulo = (
                self.t("Senha incorreta")
                if isinstance(erro, SenhaIncorreta)
                else self.t("Falha ao abrir a carteira")
            )
            self.aviso(titulo, mensagem, cor=ERRO)

        self.operacao(lambda: self.trocar_carteira(self.no.abrir, nome, senha), self.atualizar, falha)

    def sair(self):
        self.operacao(lambda: self.trocar_carteira(self.no.sair), self.atualizar)

    def trocar_carteira(self, acao, *argumentos):
        acao(*argumentos)
        return self.no.estado(ITENS_HISTORICO)

    def receber(self):
        self.operacao(self.no.receber, self.exibir_endereco)

    def exibir_endereco(self, endereco, atualizar=False):
        janela = tk.Toplevel(self.janela)
        janela.title(self.t("Receber REAL-26"))
        janela.configure(bg=PAINEL)
        janela.transient(self.janela)
        janela.grab_set()
        self.texto(janela, self.t("Endereço de recebimento"), tamanho=19, peso="bold").pack(
            anchor="w", padx=22, pady=(22, 10)
        )
        self.texto(janela, endereco, wraplength=530, justify="left").pack(anchor="w", padx=22)
        self.botao(
            janela, self.t("Copiar endereço"), lambda: (self.copiar(endereco), janela.destroy()), True
        ).pack(anchor="w", padx=22, pady=18)
        self.estado.config(text=self.t("Endereço de teste disponível."))
        if atualizar:
            self.operacao(self.ler_estado, self.atualizar)

    def enviar(self):
        formulario = tk.Toplevel(self.janela)
        formulario.title(self.t("Enviar REAL-26"))
        formulario.configure(bg=PAINEL)
        formulario.transient(self.janela)
        formulario.grab_set()
        formulario.after_idle(lambda: self.colorir_titulo(formulario) if formulario.winfo_exists() else None)
        self.texto(formulario, self.t("Enviar REAL-26"), tamanho=20, peso="bold").pack(
            anchor="w", padx=22, pady=(20, 8)
        )
        campos = []
        for titulo, inicial, oculta in (
            (self.t("Endereço do destinatário"), "", ""),
            (self.t("Valor"), "", ""),
            (self.t("Senha da carteira"), "", "●"),
        ):
            self.texto(formulario, titulo, cor=SUAVE).pack(anchor="w", padx=22, pady=(7, 2))
            campo = tk.Entry(
                formulario,
                width=58,
                bg=FUNDO,
                fg=TEXTO,
                insertbackground=TEXTO,
                relief="flat",
                font=(FONTE, 11),
                show=oculta,
            )
            campo.pack(fill="x", padx=22, ipady=5)
            campo.insert(0, inicial)
            campos.append(campo)

        def ocupado(sim):
            for widget in (*campos, botao):
                widget.config(state="disabled" if sim else "normal")
            formulario.protocol("WM_DELETE_WINDOW", (lambda: None) if sim else formulario.destroy)

        def confirmar():
            endereco, valor, senha = (campo.get() for campo in campos)
            endereco, valor = endereco.strip(), valor.strip()
            ocupado(True)

            def cotacao(taxa):
                rede = self.t("Rede de teste compartilhada" if self.compartilhado else "Rede de teste isolada")
                detalhes = self.t(
                    "{0}\n\nValor  {1} REAL-26\nTaxa automática  {2} REAL-26\n\nDestino\n{3}",
                    rede,
                    valor,
                    self.moedas(taxa),
                    endereco,
                )
                if not self.aviso(
                    self.t("Confirmar envio de teste"), detalhes, pai=formulario, confirmar=self.t("Enviar")
                ):
                    ocupado(False)
                    return
                campos[-1].config(state="normal")
                campos[-1].delete(0, tk.END)
                campos[-1].config(state="disabled")
                self.operacao(lambda: self.no.enviar(endereco, valor, taxa, senha), enviado, falha)

            def falha_cotacao(_, mensagem):
                self.aviso(self.t("Falha ao calcular a taxa"), mensagem, pai=formulario, cor=ERRO)
                ocupado(False)

            self.operacao(lambda: self.no.estimar_taxa(endereco, valor), cotacao, falha_cotacao)

        def enviado(resultado):
            formulario.destroy()
            self.enviado(resultado)

        def falha(erro, mensagem):
            if isinstance(erro, SenhaIncorreta):
                self.aviso(self.t("Senha incorreta"), mensagem, pai=formulario, cor=ERRO)
                ocupado(False)
                campos[-1].focus_set()
            else:
                formulario.destroy()
                self.aviso(self.t("Falha no envio"), mensagem, cor=ERRO)

        botao = self.botao(formulario, self.t("Conferir envio"), confirmar, True)
        botao.pack(anchor="w", padx=22, pady=19)
        campos[0].focus_set()

    def enviado(self, resultado):
        txid, aviso = resultado
        mensagem = self.t("Identificador da transação:\n{0}", txid)
        if aviso:
            mensagem += "\n\n" + self.t(aviso)
        self.aviso(self.t("Pagamento submetido"), mensagem, cor=DOURADO if aviso else VERDE)
        self.operacao(self.ler_estado, self.atualizar)

    def backup(self):
        caminho = filedialog.asksaveasfilename(
            parent=self.janela,
            title=self.t("Salvar backup criptografado"),
            defaultextension=".dat",
            initialfile="real26-backup.dat",
        )
        if caminho:
            self.operacao(
                lambda: self.no.backup(caminho),
                lambda _: self.aviso(
                    self.t("Backup salvo"),
                    self.t("O backup criptografado passou pela verificação de integridade."),
                    cor=VERDE,
                ),
                lambda _, mensagem: self.aviso(self.t("Falha ao salvar backup"), mensagem, cor=ERRO),
            )

    def restaurar(self):
        caminho = filedialog.askopenfilename(parent=self.janela, title=self.t("Abrir backup REAL-26"))
        if caminho:
            nome = self.pedir(self.t("Restaurar backup"), self.t("Nome para a carteira restaurada"))
            if nome and nome.strip():
                nome = nome.strip()

                def restaurada(_):
                    self.estado.config(
                        text=self.t("Backup restaurado. Informe a senha original para abrir a carteira.")
                    )
                    self.pedir_senha_para_abrir(nome)

                self.operacao(
                    lambda: self.no.restaurar(caminho, nome),
                    restaurada,
                    lambda _, mensagem: self.aviso(self.t("Falha ao restaurar backup"), mensagem, cor=ERRO),
                )


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--datadir", help="Diretório de dados do nó.")
    parser.add_argument("--rpcport", type=int, help="Porta RPC local.")
    parser.add_argument("--testnet", action="store_true", help="Abre a testnet compartilhada.")
    parser.add_argument(
        "--par",
        action="append",
        default=[],
        metavar="ENDERECO",
        help="Conecta ao endereço indicado na testnet ASERT. Pode ser repetido.",
    )
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--wsl", action="store_true", help="Abre o nó e a carteira da edição anterior no WSL.")
    modo.add_argument("--binarios", type=Path, help="Diretório com os executáveis nativos do nó.")
    args = parser.parse_args()
    if args.wsl and (args.testnet or args.par):
        parser.error("O teste compartilhado neste aplicativo requer a edição nativa.")
    janela = tk.Tk()
    binarios = None if args.wsl else args.binarios or Path(__file__).resolve().parents[1] / "no-windows"
    try:
        iniciais = NoReal26.ler_pares_iniciais(ARTES / "pares-testnet.txt") if args.testnet else ()
        no = NoReal26(
            args.datadir,
            args.rpcport,
            binarios=binarios,
            pares=(*args.par, *iniciais),
            compartilhado=args.testnet,
        )
    except (ErroNo, OSError) as erro:
        parser.error(str(erro))
    Carteira(janela, no)
    janela.mainloop()
