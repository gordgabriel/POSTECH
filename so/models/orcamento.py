import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from so.models.ordem_servico import OrdemServico, StatusOS


class Orcamento(models.Model):
    """N:1 com a OS: sequência 1 é o inicial, 2 em diante são os adicionais."""

    class Status(models.TextChoices):
        PENDENTE = 'pendente', 'Pendente'
        APROVADO = 'aprovado', 'Aprovado'
        RECUSADO = 'recusado', 'Recusado'
        EXPIRADO = 'expirado', 'Expirado'

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    ordem_servico = models.ForeignKey(
        OrdemServico,
        on_delete=models.CASCADE,
        related_name='orcamentos',
    )
    sequencia = models.PositiveIntegerField()
    # Soma dos itens gravada na geração — invariante do domínio.
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

    @classmethod
    @transaction.atomic
    def gerar_para_os(cls, ordem_servico):
        """Vincula os itens ainda sem orçamento e congela o valor total."""
        itens_servico = ordem_servico.itens_servico.filter(orcamento__isnull=True)
        itens_peca = ordem_servico.itens_peca.filter(orcamento__isnull=True)
        if not itens_servico.exists() and not itens_peca.exists():
            raise ValidationError(
                'A OS não possui itens pendentes de orçamento.',
            )

        ultima = (
            ordem_servico.orcamentos.aggregate(models.Max('sequencia'))['sequencia__max']
            or 0
        )
        valor_total = sum(
            (item.subtotal for item in itens_servico),
            Decimal('0.00'),
        ) + sum(
            (item.subtotal for item in itens_peca),
            Decimal('0.00'),
        )

        orcamento = cls.objects.create(
            ordem_servico=ordem_servico,
            sequencia=ultima + 1,
            valor_total=valor_total,
        )
        itens_servico.update(orcamento=orcamento)
        itens_peca.update(orcamento=orcamento)

        if ordem_servico.status == StatusOS.EM_DIAGNOSTICO:
            ordem_servico.transitar_para(StatusOS.AGUARDANDO_APROVACAO)

        return orcamento

    def responder(self, aprovado):
        if self.status != self.Status.PENDENTE:
            raise ValidationError(
                f'Orçamento já respondido (status atual: {self.status}).',
            )
        self.status = self.Status.APROVADO if aprovado else self.Status.RECUSADO
        self.data_resposta = timezone.now()
        self.save(update_fields=['status', 'data_resposta'])

        os_ = self.ordem_servico
        if aprovado and os_.status == StatusOS.AGUARDANDO_APROVACAO:
            os_.transitar_para(StatusOS.EM_EXECUCAO)

    def __str__(self):
        return f'Orçamento {self.sequencia} da OS {self.ordem_servico.uuid}'
