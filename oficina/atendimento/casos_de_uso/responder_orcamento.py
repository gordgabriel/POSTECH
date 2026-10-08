from oficina.atendimento.dominio.orcamento import destino_apos_recusa
from oficina.atendimento.dominio.ordem_servico import StatusOS
from oficina.estoque.dominio.erros import EstoqueInsuficiente


class ResponderOrcamento:
    """Comandos Aprovar e Recusar orçamento."""

    def __init__(self, orcamentos, ordens, transitar, reservar_itens, notificador, relogio):
        self.orcamentos = orcamentos
        self.ordens = ordens
        self.transitar = transitar
        self.reservar_itens = reservar_itens
        self.notificador = notificador
        self.relogio = relogio

    def executar(self, orcamento_id, aprovado):
        orcamento = self.orcamentos.obter(orcamento_id)
        ordem_servico = self.ordens.obter(orcamento.ordem_servico_id)
        orcamento.validar_resposta(ordem_servico.status)

        if aprovado:
            # Faltando peça, a resposta não é gravada e a OS fica retida.
            try:
                self.reservar_itens.executar(self.orcamentos.itens_peca(orcamento_id))
            except EstoqueInsuficiente as exc:
                self.notificador.estoque_insuficiente(ordem_servico.id, exc.faltantes)
                raise

        orcamento.registrar_resposta(aprovado, self.relogio.agora())
        self.orcamentos.salvar(orcamento, ['status', 'data_resposta'])

        if aprovado:
            self.transitar.executar(ordem_servico.id, StatusOS.EM_EXECUCAO)
            return orcamento

        self.orcamentos.descartar_itens(orcamento_id)
        ja_autorizou = self.ordens.possui_orcamento_aprovado(ordem_servico.id)
        self.transitar.executar(ordem_servico.id, destino_apos_recusa(ja_autorizou))
        return orcamento
