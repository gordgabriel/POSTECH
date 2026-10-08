from oficina.atendimento.dominio.ordem_servico import StatusOS


class TransitarOS:
    # E-mail e baixa ficam em EfeitosDaTransicao, disparados no save da OS.
    def __init__(self, ordens, relogio):
        self.ordens = ordens
        self.relogio = relogio

    def executar(self, os_id, novo_status):
        ordem_servico = self.ordens.obter(os_id)
        if ordem_servico.transitar_para(novo_status, self.relogio.agora()):
            self.ordens.salvar(ordem_servico)
        return ordem_servico


class EfeitosDaTransicao:
    """E-mail ao cliente a cada etapa e baixa do estoque na entrega."""

    def __init__(self, ordens, notificador, baixar_itens):
        self.ordens = ordens
        self.notificador = notificador
        self.baixar_itens = baixar_itens

    def executar(self, os_id, status_novo, status_anterior):
        self.notificador.status_alterado(os_id, status_anterior)
        if status_novo == StatusOS.ENTREGUE:
            self.baixar_itens.executar(self.ordens.itens_peca_reservados(os_id))
