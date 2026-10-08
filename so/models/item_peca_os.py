from django.db import models

from estoque.models import Peca
from oficina.atendimento.dominio import itens as dominio
from so.models.item_base import ItemOSBase
from so.models.ordem_servico import OrdemServico


class ItemPecaOS(ItemOSBase):
    ordem_servico = models.ForeignKey(
        OrdemServico,
        on_delete=models.CASCADE,
        related_name='itens_peca',
    )
    peca = models.ForeignKey(
        Peca,
        on_delete=models.PROTECT,
        related_name='itens_os',
    )
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
        return dominio.esta_reservado(self._orcamento(self._casos()))

    def __str__(self):
        return f'{self.quantidade}x {self.peca.nome}'
