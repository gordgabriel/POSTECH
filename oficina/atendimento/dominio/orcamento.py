from dataclasses import dataclass
from decimal import Decimal

from oficina.atendimento.dominio.erros import OrcamentoInvalido, SemItensPendentes
from oficina.atendimento.dominio.ordem_servico import StatusOS
from oficina.enumeracao import Enumeracao


class StatusOrcamento(Enumeracao):
    PENDENTE = 'pendente', 'Pendente'
    APROVADO = 'aprovado', 'Aprovado'
    RECUSADO = 'recusado', 'Recusado'


STATUS_OS_QUE_PERMITEM_ENVIO = (StatusOS.EM_DIAGNOSTICO, StatusOS.EM_EXECUCAO)


def proxima_sequencia(ultima):
    return (ultima or 0) + 1


def exigir_itens_pendentes(ha_itens_pendentes, orcamento_aberto):
    if not ha_itens_pendentes and orcamento_aberto is None:
        raise SemItensPendentes('A OS não possui itens pendentes de orçamento.')


def destino_apos_recusa(ja_autorizou):
    # Recusa de adicional volta para execução; na negociação inicial, para diagnóstico.
    if ja_autorizou:
        return StatusOS.EM_EXECUCAO
    return StatusOS.EM_DIAGNOSTICO


@dataclass
class Orcamento:
    """Antes da primeira aprovação, cada orçamento é nova proposta; depois, reparo adicional."""

    id: object
    ordem_servico_id: object
    sequencia: int
    status: str = StatusOrcamento.PENDENTE
    valor_total: Decimal = Decimal('0.00')
    data_envio: object = None
    data_resposta: object = None

    @property
    def em_aberto(self):
        return self.status == StatusOrcamento.PENDENTE and self.data_envio is None

    @property
    def aguardando_resposta(self):
        return self.status == StatusOrcamento.PENDENTE and self.data_envio is not None

    @property
    def aprovado(self):
        return self.status == StatusOrcamento.APROVADO

    def atualizar_total(self, subtotais_servico, subtotais_peca):
        total = sum(subtotais_servico, Decimal('0.00')) + sum(
            subtotais_peca, Decimal('0.00'),
        )
        if total == self.valor_total:
            return False
        self.valor_total = total
        return True

    def enviar(self, status_os, agora):
        if self.status != StatusOrcamento.PENDENTE:
            raise OrcamentoInvalido(
                f'Só é possível enviar orçamento pendente '
                f'(status atual: {self.status}).',
            )
        if status_os not in STATUS_OS_QUE_PERMITEM_ENVIO:
            raise OrcamentoInvalido(
                f'Não é possível enviar orçamento com a OS em '
                f'"{StatusOS.rotulo_de(status_os)}". A OS precisa estar em '
                f'diagnóstico, ou em execução no caso de reparo adicional.',
            )
        if self.data_envio is not None:
            return False
        self.data_envio = agora
        return True

    def validar_resposta(self, status_os):
        if self.status != StatusOrcamento.PENDENTE:
            raise OrcamentoInvalido(
                f'Orçamento já respondido (status atual: {self.status}).',
            )
        if status_os != StatusOS.AGUARDANDO_APROVACAO:
            raise OrcamentoInvalido(
                f'Não é possível responder um orçamento com a OS em '
                f'"{StatusOS.rotulo_de(status_os)}". Envie o orçamento ao cliente '
                f'antes de registrar a resposta.',
            )

    def registrar_resposta(self, aprovado, agora):
        self.status = StatusOrcamento.APROVADO if aprovado else StatusOrcamento.RECUSADO
        self.data_resposta = agora
