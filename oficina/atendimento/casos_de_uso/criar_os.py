class CriarOS:
    def __init__(self, ordens):
        self.ordens = ordens

    def executar(self, dados):
        return self.ordens.criar(dados)
