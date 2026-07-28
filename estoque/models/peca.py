import uuid

from django.db import models


class Peca(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.CharField(max_length=254, blank=True)
    # Sem o preço da peça o orçamento não tem de onde somar.
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    quantidade = models.PositiveIntegerField(default=0)
    quantidade_reservada = models.PositiveIntegerField(default=0)
    # Sustenta a política "estoque abaixo do mínimo -> alertar reposição".
    estoque_minimo = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'peça'
        verbose_name_plural = 'peças'

    @property
    def quantidade_disponivel(self):
        return self.quantidade - self.quantidade_reservada

    @property
    def abaixo_do_minimo(self):
        return self.quantidade_disponivel < self.estoque_minimo

    def __str__(self):
        return self.nome
