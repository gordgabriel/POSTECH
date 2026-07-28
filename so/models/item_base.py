import uuid

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
