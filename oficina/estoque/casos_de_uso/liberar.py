class LiberarPeca:
    def __init__(self, pecas, unidade):
        self.pecas = pecas
        self.unidade = unidade

    def executar(self, peca_id, quantidade):
        with self.unidade.atomico():
            peca = self.pecas.travar(peca_id)
            peca.liberar(quantidade)
            self.pecas.salvar(peca, ['quantidade_reservada'])


class LiberarItens:
    def __init__(self, unidade, liberar_peca):
        self.unidade = unidade
        self.liberar_peca = liberar_peca

    def executar(self, itens):
        with self.unidade.atomico():
            for peca_id, quantidade in itens:
                self.liberar_peca.executar(peca_id, quantidade)
