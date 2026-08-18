import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from cadastros.models import Cliente, Veiculo
from estoque.services import EstoqueService


class StatusOS(models.TextChoices):
    """As seis etapas do atendimento. Encerrar uma OS não é etapa: é baixa,
    registrada em is_active, e o status guarda até onde o serviço chegou."""

    RECEBIDA = 'Recebida', 'Recebida'
    EM_DIAGNOSTICO = 'EmDiagnostico', 'Em diagnóstico'
    AGUARDANDO_APROVACAO = 'AguardandoAprovacao', 'Aguardando aprovação'
    EM_EXECUCAO = 'EmExecucao', 'Em execução'
    FINALIZADA = 'Finalizada', 'Finalizada'
    ENTREGUE = 'Entregue', 'Entregue'


# Invariante: o status só transita na sequência válida. Há dois retornos:
# EmExecucao -> AguardandoAprovacao no reparo adicional, e
# AguardandoAprovacao -> EmDiagnostico quando o cliente recusa o orçamento e
# o mecânico refaz a proposta.
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

# Cada transição alimenta a data que sustenta o relatório de tempo médio.
DATA_POR_STATUS = {
    StatusOS.EM_DIAGNOSTICO: 'data_diagnostico',
    StatusOS.EM_EXECUCAO: 'data_inicio_execucao',
    StatusOS.FINALIZADA: 'data_finalizacao',
    StatusOS.ENTREGUE: 'data_entrega',
}


class OrdemServico(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    # Queixa do cliente registrada na abertura.
    descricao = models.TextField()
    # Preenchido pelo mecânico no evento "Diagnóstico realizado".
    diagnostico = models.TextField(null=True, blank=True)
    observacoes = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=30,
        choices=StatusOS.choices,
        default=StatusOS.RECEBIDA,
    )
    # PROTECT: OS é registro histórico, não se apaga em cascata.
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='ordens_servico',
    )
    veiculo = models.ForeignKey(
        Veiculo,
        on_delete=models.PROTECT,
        related_name='ordens_servico',
    )
    data_abertura = models.DateTimeField(auto_now_add=True)
    data_diagnostico = models.DateTimeField(null=True, blank=True)
    data_inicio_execucao = models.DateTimeField(null=True, blank=True)
    data_finalizacao = models.DateTimeField(null=True, blank=True)
    data_entrega = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'ordem de serviço'
        verbose_name_plural = 'ordens de serviço'

    @staticmethod
    def validar_transicao(status_atual, novo_status):
        permitidos = TRANSICOES_VALIDAS.get(status_atual, set())
        if novo_status not in permitidos:
            raise ValidationError({
                'status': (
                    f'Transição inválida: "{status_atual}" não pode ir para '
                    f'"{novo_status}". Transições permitidas: '
                    f'{sorted(permitidos) or "nenhuma"}.'
                ),
            })

    def transitar_para(self, novo_status):
        """Transição validada com registro de datas e efeitos colaterais de estoque."""
        if self.status == novo_status:
            return
        self.validar_transicao(self.status, novo_status)
        self.status = novo_status
        campo_data = DATA_POR_STATUS.get(novo_status)
        if campo_data and getattr(self, campo_data) is None:
            setattr(self, campo_data, timezone.now())
        self.save()

    def encerrar(self):
        """
        Baixa do atendimento: o registro sai de circulação e o histórico fica.

        Encerrar não é etapa do serviço, por isso não mexe no status — ele
        continua marcando até onde o atendimento chegou antes de ser encerrado.
        As peças reservadas voltam ao estoque.
        """
        if not self.is_active:
            raise ValidationError({'is_active': 'Esta OS já está encerrada.'})
        if self.status == StatusOS.ENTREGUE:
            raise ValidationError({
                'is_active': (
                    'OS entregue está concluída e não se encerra: o serviço '
                    'foi prestado.'
                ),
            })

        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])
        EstoqueService.liberar_itens_os(self)

        from notifications.services.os_notifications import notificar_os_encerrada
        notificar_os_encerrada(self)
        return self

    def save(self, *args, **kwargs):
        baixar_estoque = False
        status_anterior = None
        notificar = False

        if self.pk:
            status_anterior = (
                OrdemServico.objects.only('status').get(pk=self.pk).status
            )
            if status_anterior != self.status:
                self.validar_transicao(status_anterior, self.status)
                campo_data = DATA_POR_STATUS.get(self.status)
                if campo_data and getattr(self, campo_data) is None:
                    setattr(self, campo_data, timezone.now())
                if self.status == StatusOS.ENTREGUE:
                    baixar_estoque = True
                notificar = True

        super().save(*args, **kwargs)

        if notificar:
            from notifications.services.os_notifications import notificar_status_os
            notificar_status_os(self, status_anterior)

        if baixar_estoque:
            EstoqueService.baixar_itens_os(self)

    def __str__(self):
        return f'OS {self.uuid} - {self.get_status_display()}'
