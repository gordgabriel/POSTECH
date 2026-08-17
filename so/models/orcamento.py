import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from estoque.services import EstoqueInsuficiente, EstoqueService
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
    def em_aberto(cls, ordem_servico):
        """O orçamento que ainda está sendo montado: pendente e não enviado."""
        return ordem_servico.orcamentos.filter(
            status=cls.Status.PENDENTE,
            data_envio__isnull=True,
        ).first()

    @transaction.atomic
    def recalcular_total(self):
        """Soma os itens vinculados. Só faz sentido antes do envio."""
        total = sum(
            (item.subtotal for item in self.itens_servico.all()),
            Decimal('0.00'),
        ) + sum(
            (item.subtotal for item in self.itens_peca.all()),
            Decimal('0.00'),
        )
        if total != self.valor_total:
            self.valor_total = total
            self.save(update_fields=['valor_total'])
        return self

    @classmethod
    @transaction.atomic
    def gerar_para_os(cls, ordem_servico):
        """
        Orçamento gerado automaticamente a partir dos serviços e peças da OS.

        Chamado sozinho a cada item incluído. Enquanto o orçamento não é
        enviado ele continua aberto e vai absorvendo os itens novos; depois do
        envio, item novo abre o orçamento seguinte, que é o reparo adicional.
        """
        itens_servico = ordem_servico.itens_servico.filter(orcamento__isnull=True)
        itens_peca = ordem_servico.itens_peca.filter(orcamento__isnull=True)

        orcamento = cls.em_aberto(ordem_servico)
        if not itens_servico.exists() and not itens_peca.exists():
            if orcamento is None:
                raise ValidationError(
                    'A OS não possui itens pendentes de orçamento.',
                )
            return orcamento.recalcular_total()

        if orcamento is None:
            ultima = ordem_servico.orcamentos.aggregate(
                models.Max('sequencia'),
            )['sequencia__max'] or 0
            orcamento = cls.objects.create(
                ordem_servico=ordem_servico,
                sequencia=ultima + 1,
            )

        itens_servico.update(orcamento=orcamento)
        itens_peca.update(orcamento=orcamento)

        # Gerar não é evento pivotal: quem muda a fase da OS é o envio.
        return orcamento.recalcular_total()

    # EmExecucao cobre o reparo adicional: a OS volta a aguardar resposta.
    STATUS_OS_QUE_PERMITEM_ENVIO = (StatusOS.EM_DIAGNOSTICO, StatusOS.EM_EXECUCAO)

    def enviar(self):
        """Comando Enviar orçamento ao cliente. Evento pivotal: muda o status."""
        if self.status != self.Status.PENDENTE:
            raise ValidationError(
                f'Só é possível enviar orçamento pendente '
                f'(status atual: {self.status}).',
            )

        os_ = self.ordem_servico
        if os_.status not in self.STATUS_OS_QUE_PERMITEM_ENVIO:
            raise ValidationError(
                f'Não é possível enviar orçamento com a OS em '
                f'"{os_.get_status_display()}". A OS precisa estar em '
                f'diagnóstico, ou em execução no caso de reparo adicional.',
            )

        if self.data_envio is None:
            self.data_envio = timezone.now()
            self.save(update_fields=['data_envio'])

        os_.transitar_para(StatusOS.AGUARDANDO_APROVACAO)
        return self

    def responder(self, aprovado):
        """Comandos Aprovar e Recusar orçamento. Evento pivotal: muda o status."""
        if self.status != self.Status.PENDENTE:
            raise ValidationError(
                f'Orçamento já respondido (status atual: {self.status}).',
            )

        os_ = self.ordem_servico
        # A resposta do cliente só existe depois do envio.
        if os_.status != StatusOS.AGUARDANDO_APROVACAO:
            raise ValidationError(
                f'Não é possível responder um orçamento com a OS em '
                f'"{os_.get_status_display()}". Envie o orçamento ao cliente '
                f'antes de registrar a resposta.',
            )

        if aprovado:
            # Política do quadro: reservar as peças da OS aprovada. Se faltar,
            # o atendente é avisado e a OS fica pausada onde está — a resposta
            # não é gravada, para que o cliente possa aprovar de novo depois.
            try:
                EstoqueService.reservar_itens_orcamento(self)
            except EstoqueInsuficiente as exc:
                from notifications.services.estoque_notifications import (
                    alertar_estoque_insuficiente,
                )
                alertar_estoque_insuficiente(os_, exc.faltantes)
                raise

        self.status = self.Status.APROVADO if aprovado else self.Status.RECUSADO
        self.data_resposta = timezone.now()
        self.save(update_fields=['status', 'data_resposta'])

        if aprovado:
            os_.transitar_para(StatusOS.EM_EXECUCAO)
        elif self.sequencia == 1:
            # Recusa do inicial: a OS volta para diagnóstico, onde o mecânico
            # revê os itens e monta outra proposta. Se o cliente desistir de
            # vez, o atendente encerra a OS.
            os_.transitar_para(StatusOS.EM_DIAGNOSTICO)
        else:
            # Recusa de adicional: nada a liberar, porque orçamento não
            # aprovado nunca reservou. A OS retoma o que já foi aprovado.
            os_.transitar_para(StatusOS.EM_EXECUCAO)

    def __str__(self):
        return f'Orçamento {self.sequencia} da OS {self.ordem_servico.uuid}'
