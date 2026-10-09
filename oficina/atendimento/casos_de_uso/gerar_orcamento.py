from oficina.atendimento.dominio.orcamento import exigir_itens_pendentes, proxima_sequencia


class RecalcularOrcamento:
    def __init__(self, orcamentos, unidade):
        self.orcamentos = orcamentos
        self.unidade = unidade

    def executar(self, orcamento_id):
        with self.unidade.atomico():
            orcamento = self.orcamentos.obter(orcamento_id)
            if orcamento.atualizar_total(*self.orcamentos.subtotais(orcamento_id)):
                self.orcamentos.salvar(orcamento, ['valor_total'])
            return orcamento


class GerarOrcamento:
    # Enquanto não é enviado, o orçamento aberto absorve os itens novos.
    def __init__(self, orcamentos, unidade, recalcular):
        self.orcamentos = orcamentos
        self.unidade = unidade
        self.recalcular = recalcular

    def executar(self, os_id):
        with self.unidade.atomico():
            aberto = self.orcamentos.em_aberto(os_id)
            ha_pendentes = self.orcamentos.ha_itens_pendentes(os_id)
            exigir_itens_pendentes(ha_pendentes, aberto)
            if not ha_pendentes:
                return self.recalcular.executar(aberto.id)

            if aberto is None:
                aberto = self.orcamentos.criar(
                    os_id,
                    proxima_sequencia(self.orcamentos.ultima_sequencia(os_id)),
                )
            self.orcamentos.vincular_itens_pendentes(os_id, aberto.id)
            return self.recalcular.executar(aberto.id)
