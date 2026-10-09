import uuid
from decimal import Decimal

from django.db import models

from oficina.atendimento.dominio import orcamento as dominio
from So_PosTech.exceptions import traduzir_erros_de_dominio
from so.models.ordem_servico import OrdemServico


class Orcamento(models.Model):
    """N:1 com a OS. A sequência só numera os orçamentos, não os classifica."""

    Status = models.TextChoices(
        'Status',
        [(status.name, (status.value, status.label)) for status in dominio.StatusOrcamento],
        module=__name__,
        qualname='Orcamento.Status',
    )

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    ordem_servico = models.ForeignKey(
        OrdemServico,
        on_delete=models.CASCADE,
        related_name='orcamentos',
    )
    sequencia = models.PositiveIntegerField()
    valor_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDENTE,
    )
    data_geracao = models.DateTimeField(auto_now_add=True)
    data_envio = models.DateTimeField(null=True, blank=True)
    data_resposta = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'orçamento'
        verbose_name_plural = 'orçamentos'
        constraints = [
            models.UniqueConstraint(
                fields=['ordem_servico', 'sequencia'],
                name='orcamento_sequencia_unica_por_os',
            ),
        ]

    STATUS_OS_QUE_PERMITEM_ENVIO = dominio.STATUS_OS_QUE_PERMITEM_ENVIO

    @classmethod
    def em_aberto(cls, ordem_servico):
        return ordem_servico.orcamentos.filter(
            status=cls.Status.PENDENTE,
            data_envio__isnull=True,
        ).first()

    def recalcular_total(self):
        from So_PosTech.container import atendimento

        atendimento(self).recalcular_orcamento.executar(self.pk)
        return self

    @classmethod
    def gerar_para_os(cls, ordem_servico):
        from So_PosTech.container import atendimento

        casos = atendimento(ordem_servico)
        with traduzir_erros_de_dominio():
            orcamento = casos.gerar_orcamento.executar(ordem_servico.pk)
        return casos.orcamentos.modelo(orcamento.id)

    def enviar(self):
        from So_PosTech.container import atendimento

        with traduzir_erros_de_dominio():
            atendimento(self).enviar_orcamento.executar(self.pk)
        return self

    def responder(self, aprovado):
        from So_PosTech.container import atendimento

        with traduzir_erros_de_dominio():
            atendimento(self).responder_orcamento.executar(self.pk, aprovado)

    def descartar_itens(self):
        from So_PosTech.container import atendimento

        atendimento(self).orcamentos.descartar_itens(self.pk)

    def __str__(self):
        return f'Orçamento {self.sequencia} da OS {self.ordem_servico.uuid}'
