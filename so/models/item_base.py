import uuid

from django.core.exceptions import ValidationError
from django.db import models


class ItemOSBase(models.Model):
    """Campos comuns aos itens de serviço e de peça da OS."""

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    quantidade = models.PositiveIntegerField(default=1)
    # Congelado na inclusão: reajuste no catálogo não muda valor já aprovado.
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

    @property
    def subtotal(self):
        return self.quantidade * self.preco_unitario

    def validar_proposta_em_avaliacao(self):
        """Item de orçamento enviado e ainda sem resposta não é alterado."""
        from so.models.orcamento import Orcamento

        if self.orcamento_id is None:
            return

        aguardando = (
            self.orcamento.status == Orcamento.Status.PENDENTE
            and self.orcamento.data_envio is not None
        )
        if aguardando:
            raise ValidationError(
                f'O orçamento {self.orcamento.sequencia} está aguardando a '
                f'resposta do cliente e não pode ser alterado. Registre a '
                f'recusa para remontar a proposta.',
            )

    def delete(self, *args, **kwargs):
        self.validar_proposta_em_avaliacao()
        return super().delete(*args, **kwargs)

    def sincronizar_orcamento(self):
        """
        Política: itens incluídos, então gerar o orçamento automaticamente.

        Item ainda sem orçamento entra no orçamento aberto da OS, criando um se
        não houver. Item que já pertence a um orçamento ainda não enviado só
        recalcula o total, para o valor acompanhar mudança de quantidade.
        """
        from so.models.orcamento import Orcamento

        if self.orcamento_id is None:
            Orcamento.gerar_para_os(self.ordem_servico)
            return

        if self.orcamento.status == Orcamento.Status.PENDENTE and (
            self.orcamento.data_envio is None
        ):
            self.orcamento.recalcular_total()
