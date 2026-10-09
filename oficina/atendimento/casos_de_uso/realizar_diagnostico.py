from oficina.atendimento.dominio.erros import ParecerObrigatorio
from oficina.atendimento.dominio.ordem_servico import StatusOS


class RealizarDiagnostico:
    def __init__(self, ordens, relogio):
        self.ordens = ordens
        self.relogio = relogio

    def executar(self, os_id, parecer):
        parecer = (parecer or '').strip()
        if not parecer:
            raise ParecerObrigatorio(
                'Informe o parecer do diagnóstico.', campo='diagnostico',
            )

        ordem_servico = self.ordens.obter(os_id)
        ordem_servico.diagnostico = parecer
        if ordem_servico.status == StatusOS.EM_DIAGNOSTICO:
            self.ordens.salvar(ordem_servico, ['diagnostico'])
            return ordem_servico

        ordem_servico.transitar_para(StatusOS.EM_DIAGNOSTICO, self.relogio.agora())
        self.ordens.salvar(ordem_servico)
        return ordem_servico
