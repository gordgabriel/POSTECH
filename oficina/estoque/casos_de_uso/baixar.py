class BaixarPeca:
    def __init__(self, pecas, unidade):
        self.pecas = pecas
        self.unidade = unidade

    def executar(self, peca_id, quantidade):
        with self.unidade.atomico():
            peca = self.pecas.travar(peca_id)
            peca.baixar(quantidade)
            self.pecas.salvar(peca, ['quantidade', 'quantidade_reservada'])


class BaixarItens:
    """Política: baixar o estoque na entrega do veículo."""

    def __init__(self, unidade, baixar_peca, alertar_reposicao):
        self.unidade = unidade
        self.baixar_peca = baixar_peca
        self.alertar_reposicao = alertar_reposicao

    def executar(self, itens):
        with self.unidade.atomico():
            for peca_id, quantidade in itens:
                self.baixar_peca.executar(peca_id, quantidade)
            ids = [peca_id for peca_id, _ in itens]
            self.unidade.ao_confirmar(lambda: self.alertar_reposicao.executar(ids))
