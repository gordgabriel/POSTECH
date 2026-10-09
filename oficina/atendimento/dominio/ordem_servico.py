from dataclasses import dataclass, field

from oficina.atendimento.dominio.erros import EncerramentoInvalido, TransicaoInvalida
from oficina.enumeracao import Enumeracao


class StatusOS(Enumeracao):
    """As seis etapas do atendimento. Encerrar não é etapa: fica em is_active."""

    RECEBIDA = 'Recebida', 'Recebida'
    EM_DIAGNOSTICO = 'EmDiagnostico', 'Em diagnóstico'
    AGUARDANDO_APROVACAO = 'AguardandoAprovacao', 'Aguardando aprovação'
    EM_EXECUCAO = 'EmExecucao', 'Em execução'
    FINALIZADA = 'Finalizada', 'Finalizada'
    ENTREGUE = 'Entregue', 'Entregue'


# Dois retornos: reparo adicional (EmExecucao -> AguardandoAprovacao) e
# recusa do orçamento (AguardandoAprovacao -> EmDiagnostico).
TRANSICOES_VALIDAS = {
    StatusOS.RECEBIDA: {StatusOS.EM_DIAGNOSTICO},
    StatusOS.EM_DIAGNOSTICO: {StatusOS.AGUARDANDO_APROVACAO},
    StatusOS.AGUARDANDO_APROVACAO: {
        StatusOS.EM_EXECUCAO,
        StatusOS.EM_DIAGNOSTICO,
    },
    StatusOS.EM_EXECUCAO: {StatusOS.FINALIZADA, StatusOS.AGUARDANDO_APROVACAO},
    StatusOS.FINALIZADA: {StatusOS.ENTREGUE},
    StatusOS.ENTREGUE: set(),
}

DATA_POR_STATUS = {
    StatusOS.EM_DIAGNOSTICO: 'data_diagnostico',
    StatusOS.EM_EXECUCAO: 'data_inicio_execucao',
    StatusOS.FINALIZADA: 'data_finalizacao',
    StatusOS.ENTREGUE: 'data_entrega',
}


@dataclass
class OrdemServico:
    id: object
    status: str
    diagnostico: object = None
    is_active: bool = True
    datas: dict = field(default_factory=dict)

    @staticmethod
    def validar_transicao(status_atual, novo_status):
        permitidos = TRANSICOES_VALIDAS.get(status_atual, set())
        if novo_status not in permitidos:
            raise TransicaoInvalida(
                f'Transição inválida: "{status_atual}" não pode ir para '
                f'"{novo_status}". Transições permitidas: '
                f'{sorted(permitidos) or "nenhuma"}.',
                campo='status',
            )

    def _carimbar_data(self, novo_status, agora):
        campo_data = DATA_POR_STATUS.get(novo_status)
        if campo_data and self.datas.get(campo_data) is None:
            self.datas[campo_data] = agora

    def transitar_para(self, novo_status, agora):
        if self.status == novo_status:
            return False
        self.validar_transicao(self.status, novo_status)
        self.status = novo_status
        self._carimbar_data(novo_status, agora)
        return True

    def confirmar_mudanca_de_status(self, status_gravado, agora):
        # Vale para qualquer gravação (admin, seeds), não só para os comandos.
        if status_gravado is None or status_gravado == self.status:
            return False
        self.validar_transicao(status_gravado, self.status)
        self._carimbar_data(self.status, agora)
        return True

    def encerrar(self):
        """Baixa do atendimento: sai de circulação, mas o status fica onde parou."""
        if not self.is_active:
            raise EncerramentoInvalido('Esta OS já está encerrada.', campo='is_active')
        if self.status == StatusOS.ENTREGUE:
            raise EncerramentoInvalido(
                'OS entregue está concluída e não se encerra: o serviço '
                'foi prestado.',
                campo='is_active',
            )
        self.is_active = False


def veiculo_pertence_ao_cliente(cliente_do_veiculo_id, cliente_id):
    return cliente_do_veiculo_id == cliente_id
