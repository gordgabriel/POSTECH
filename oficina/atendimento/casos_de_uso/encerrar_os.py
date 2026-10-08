class EncerrarOS:
    def __init__(self, ordens, notificador, liberar_itens):
        self.ordens = ordens
        self.notificador = notificador
        self.liberar_itens = liberar_itens

    def executar(self, os_id):
        ordem_servico = self.ordens.obter(os_id)
        ordem_servico.encerrar()
        self.ordens.salvar(ordem_servico, ['is_active'])
        self.liberar_itens.executar(self.ordens.itens_peca_reservados(os_id))
        self.notificador.os_encerrada(os_id)
        return ordem_servico
