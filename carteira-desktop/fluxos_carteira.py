# Distribuído sob a licença MIT. Consulte COPYING.
"""Fluxos da carteira para abertura, pagamentos e recuperação."""

import tkinter as tk
from tkinter import filedialog

from dialogos import SeletorCarteira
from no_real26 import MINIMO_SENHA_NOVA, SenhaIncorreta
from tema import DOURADO, ERRO, FONTE, FUNDO, PAINEL, SUAVE, TEXTO, VERDE


ITENS_HISTORICO = 50


class FluxosCarteira:
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
