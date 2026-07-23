from django.db import models


class PecaEstoque(models.Model):
    nome = models.CharField(max_length=255)
    quantidade = models.IntegerField(default=0)
    quantidade_reservada = models.IntegerField(default=0)
    descricao = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nome
