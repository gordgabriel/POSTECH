from oficina.atendimento.dominio.ordem_servico import StatusOS


class EnviarOrcamento:
    def __init__(self, orcamentos, ordens, transitar, relogio):
        self.orcamentos = orcamentos
        self.ordens = ordens
        self.transitar = transitar
        self.relogio = relogio

    def executar(self, orcamento_id):
        orcamento = self.orcamentos.obter(orcamento_id)
        ordem_servico = self.ordens.obter(orcamento.ordem_servico_id)

        if orcamento.enviar(ordem_servico.status, self.relogio.agora()):
            self.orcamentos.salvar(orcamento, ['data_envio'])

        self.transitar.executar(ordem_servico.id, StatusOS.AGUARDANDO_APROVACAO)
        return orcamento
