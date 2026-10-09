from django.db import models

from cadastros.models import Servico
from so.models.item_base import ItemOSBase
from so.models.ordem_servico import OrdemServico


class ItemServicoOS(ItemOSBase):
    ordem_servico = models.ForeignKey(
        OrdemServico,
        on_delete=models.CASCADE,
        related_name='itens_servico',
    )
    servico = models.ForeignKey(
        Servico,
        on_delete=models.PROTECT,
        related_name='itens_os',
    )
    # Item incluído durante a execução fica sem orçamento até o adicional.
    orcamento = models.ForeignKey(
        'so.Orcamento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='itens_servico',
    )

    class Meta:
        verbose_name = 'item de serviço da OS'
        verbose_name_plural = 'itens de serviço da OS'

    def __str__(self):
        return f'{self.quantidade}x {self.servico.nome}'
