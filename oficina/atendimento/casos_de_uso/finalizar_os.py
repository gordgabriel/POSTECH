from oficina.atendimento.dominio.ordem_servico import StatusOS


class FinalizarOS:
    def __init__(self, transitar):
        self.transitar = transitar

    def executar(self, os_id):
        return self.transitar.executar(os_id, StatusOS.FINALIZADA)
