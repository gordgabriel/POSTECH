import uuid

from django.conf import settings
from django.db import models
from django.db.models import Value
from django.db.models.functions import Replace

from cadastros.validators import somente_digitos, validar_cpf_cnpj


class ClienteQuerySet(models.QuerySet):
    def por_documento(self, valor):
        # Compara só os dígitos.
        digitos = somente_digitos(valor)
        if not digitos:
            return self.none()
        return self.annotate(
            documento=Replace(
                Replace(
                    Replace('cpf_cnpj', Value('.'), Value('')),
                    Value('-'), Value(''),
                ),
                Value('/'), Value(''),
            ),
        ).filter(documento=digitos)


class Cliente(models.Model):
    """Dado de domínio separado do login: nem todo cliente acessa a API."""

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    cpf_cnpj = models.CharField(
        max_length=18,
        unique=True,
        validators=[validar_cpf_cnpj],
        verbose_name='CPF/CNPJ',
    )
    nome = models.CharField(max_length=100)
    email = models.EmailField(max_length=254)
    telefone = models.CharField(max_length=15, null=True, blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    endereco = models.TextField(null=True, blank=True)
    # Opcional: só o cliente que consulta a OS pela API precisa de login.
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cliente',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ClienteQuerySet.as_manager()

    class Meta:
        verbose_name = 'cliente'
        verbose_name_plural = 'clientes'

    def __str__(self):
        return f'{self.nome} ({self.cpf_cnpj})'
