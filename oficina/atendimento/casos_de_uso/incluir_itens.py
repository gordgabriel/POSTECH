from oficina.atendimento.dominio.itens import (
    ajuste_de_reserva,
    esta_reservado,
    preco_congelado,
    validar_proposta_em_avaliacao,
)


class SincronizarOrcamento:
    """Política: itens incluídos, então gerar o orçamento automaticamente."""

    def __init__(self, orcamentos, gerar, recalcular):
        self.orcamentos = orcamentos
        self.gerar = gerar
        self.recalcular = recalcular

    def executar(self, item):
        if item.orcamento_id is None:
            self.gerar.executar(item.ordem_servico_id)
            return
        if self.orcamentos.obter(item.orcamento_id).em_aberto:
            self.recalcular.executar(item.orcamento_id)


class _ComandoDeItem:
    def __init__(self, itens, orcamentos, unidade):
        self.itens = itens
        self.orcamentos = orcamentos
        self.unidade = unidade

    def _orcamento(self, item):
        if item.orcamento_id is None:
            return None
        return self.orcamentos.obter(item.orcamento_id)


class SalvarItem(_ComandoDeItem):
    """Comando Incluir itens: congela o preço e mantém o orçamento em dia."""

    def __init__(self, itens, orcamentos, unidade, sincronizar, reservar_peca, liberar_peca):
        super().__init__(itens, orcamentos, unidade)
        self.sincronizar = sincronizar
        self.reservar_peca = reservar_peca
        self.liberar_peca = liberar_peca

    def executar(self, item):
        item.preco_unitario = preco_congelado(
            item.preco_unitario, lambda: self.itens.preco_de_catalogo(item),
        )
        if not item.novo:
            validar_proposta_em_avaliacao(self._orcamento(item))

        if not item.eh_peca:
            self.itens.gravar(item)
            self.sincronizar.executar(item)
            return item

        with self.unidade.atomico():
            # Só item já aprovado acompanha a mudança de quantidade no estoque.
            if not item.novo and esta_reservado(self._orcamento(item)):
                diferenca = ajuste_de_reserva(
                    self.itens.quantidade_gravada(item.id), item.quantidade,
                )
                if diferenca > 0:
                    self.reservar_peca.executar(item.peca_id, diferenca)
                elif diferenca < 0:
                    self.liberar_peca.executar(item.peca_id, -diferenca)
            self.itens.gravar(item)
            self.sincronizar.executar(item)
        return item


class RemoverItem(_ComandoDeItem):
    def __init__(self, itens, orcamentos, unidade, liberar_peca):
        super().__init__(itens, orcamentos, unidade)
        self.liberar_peca = liberar_peca

    def executar(self, item):
        validar_proposta_em_avaliacao(self._orcamento(item))
        if not item.eh_peca:
            return self.itens.remover(item)

        with self.unidade.atomico():
            if esta_reservado(self._orcamento(item)):
                self.liberar_peca.executar(item.peca_id, item.quantidade)
            return self.itens.remover(item)
