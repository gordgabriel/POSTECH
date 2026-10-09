from oficina.estoque.dominio.peca import conferir_saldo, somar_necessario


class ReservarPeca:
    def __init__(self, pecas, unidade):
        self.pecas = pecas
        self.unidade = unidade

    def executar(self, peca_id, quantidade):
        with self.unidade.atomico():
            peca = self.pecas.travar(peca_id)
            peca.reservar(quantidade)
            self.pecas.salvar(peca, ['quantidade_reservada'])


class ReservarItensDoOrcamento:
    """Política: reservar as peças do orçamento aprovado."""

    def __init__(self, pecas, unidade, reservar_peca, alertar_reposicao):
        self.pecas = pecas
        self.unidade = unidade
        self.reservar_peca = reservar_peca
        self.alertar_reposicao = alertar_reposicao

    def executar(self, itens):
        with self.unidade.atomico():
            if not itens:
                return itens

            necessario = somar_necessario(itens)
            conferir_saldo(self.pecas.travar_varias(list(necessario)), necessario)

            for peca_id, quantidade in itens:
                self.reservar_peca.executar(peca_id, quantidade)
            ids = [peca_id for peca_id, _ in itens]
            self.unidade.ao_confirmar(lambda: self.alertar_reposicao.executar(ids))
            return itens
