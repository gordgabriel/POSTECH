class AlertarReposicao:
    def __init__(self, pecas, alerta):
        self.pecas = pecas
        self.alerta = alerta

    def executar(self, pecas_ids):
        return self.alerta.estoque_minimo(self.pecas.obter_varias(pecas_ids))
