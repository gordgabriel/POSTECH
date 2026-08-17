from django.db import models, transaction

from estoque.models import Peca
from estoque.services import EstoqueService
from so.models.item_base import ItemOSBase
from so.models.ordem_servico import OrdemServico


class ItemPecaOS(ItemOSBase):
    # CASCADE: o item é parte do agregado, não vive sem a OS.
    ordem_servico = models.ForeignKey(
        OrdemServico,
        on_delete=models.CASCADE,
        related_name='itens_peca',
    )
    # PROTECT: única travessia entre os contextos Atendimento e Estoque.
    peca = models.ForeignKey(
        Peca,
        on_delete=models.PROTECT,
        related_name='itens_os',
    )
    # SET_NULL: indica qual orçamento congelou o preço deste item.
    orcamento = models.ForeignKey(
        'so.Orcamento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='itens_peca',
    )

    class Meta:
        verbose_name = 'item de peça da OS'
        verbose_name_plural = 'itens de peça da OS'

    @property
    def esta_reservado(self):
        """A peça só segura estoque depois que o cliente aprova o orçamento."""
        from so.models.orcamento import Orcamento

        return (
            self.orcamento_id is not None
            and self.orcamento.status == Orcamento.Status.APROVADO
        )

    def save(self, *args, **kwargs):
        if self.preco_unitario is None:
            self.preco_unitario = self.peca.preco

        # Incluir item é montar a proposta, e proposta não segura peça: a
        # reserva acontece na aprovação do orçamento.
        with transaction.atomic():
            if self.pk is not None and self.esta_reservado:
                anterior = ItemPecaOS.objects.get(pk=self.pk)
                diff = self.quantidade - anterior.quantidade
                if diff > 0:
                    EstoqueService.reservar(self.peca, diff)
                elif diff < 0:
                    EstoqueService.liberar(self.peca, -diff)
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            if self.esta_reservado:
                EstoqueService.liberar(self.peca, self.quantidade)
            super().delete(*args, **kwargs)

    def __str__(self):
        return f'{self.quantidade}x {self.peca.nome}'
