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
    def is_operador(self):
        return bool(self.type) or self.is_staff

    def __str__(self):
        return self.username

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
