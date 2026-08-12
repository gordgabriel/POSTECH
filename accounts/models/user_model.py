import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class UserModel(AbstractUser):
    """Quem opera o sistema. Dados de cliente vivem em cadastros.Cliente."""

    class Tipo(models.TextChoices):
        ATENDENTE = 'atendente', 'Atendente'
        MECANICO = 'mecanico', 'Mecânico'
        ESTOQUISTA = 'estoquista', 'Estoquista'
        ADMIN = 'admin', 'Admin'

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=100, null=True, blank=True)
    email = models.EmailField(unique=True)
    # Vazio significa login de cliente (acesso via cadastros.Cliente.usuario).
    type = models.CharField(
        max_length=20,
        choices=Tipo.choices,
        null=True,
        blank=True,
    )
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_admin(self) -> bool:
        return self.is_staff or self.is_superuser or self.type == self.Tipo.ADMIN

    @property
    def is_atendente(self) -> bool:
        return self.type == self.Tipo.ATENDENTE

    @property
    def is_mecanico(self) -> bool:
        return self.type == self.Tipo.MECANICO

    @property
    def is_estoquista(self) -> bool:
        return self.type == self.Tipo.ESTOQUISTA

    @property
    def is_operador(self) -> bool:
        return self.is_admin or self.type in (
            self.Tipo.ATENDENTE,
            self.Tipo.MECANICO,
            self.Tipo.ESTOQUISTA,
        )

    @property
    def is_cliente(self) -> bool:
        return self.is_authenticated and not self.is_operador

    def __str__(self):
        return self.username

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
