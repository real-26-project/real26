# Distribuído sob a licença MIT. Consulte COPYING.
"""Diálogos de entrada e seleção da carteira."""

from tkinter import simpledialog, ttk


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
