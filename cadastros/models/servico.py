import uuid

from django.db import models


class Servico(models.Model):
    """Catálogo de serviços da oficina, referenciado pelos itens da OS."""

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.CharField(max_length=254, blank=True)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    tempo_execucao = models.PositiveIntegerField(
        help_text='Tempo estimado de execução, em minutos.',
    )
    # Serviço fora de linha não some do histórico: apenas deixa de ser ofertado.
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'serviço'
        verbose_name_plural = 'serviços'

    def __str__(self):
        return self.nome
