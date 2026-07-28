import uuid

from django.db import models

from cadastros.models.cliente import Cliente
from cadastros.validators import validar_placa


class Veiculo(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    # Value object Placa: única e sempre vinculada a exatamente um cliente.
    placa = models.CharField(max_length=8, unique=True, validators=[validar_placa])
    marca = models.CharField(max_length=255)
    modelo = models.CharField(max_length=255)
    ano = models.IntegerField()
    observacao = models.TextField(null=True, blank=True)
    # PROTECT: veículo pertence ao cliente e sustenta o histórico por veículo.
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='veiculos',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'veículo'
        verbose_name_plural = 'veículos'

    def save(self, *args, **kwargs):
        if self.placa:
            self.placa = self.placa.upper().replace('-', '')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.placa} - {self.marca} {self.modelo}'
