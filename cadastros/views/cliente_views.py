import re

from django.db.models import Value
from django.db.models.functions import Replace
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsAtendente, PermissoesPorAcaoMixin
from cadastros.models import Cliente
from cadastros.serializers import ClienteSerializer


class ClienteViewSet(PermissoesPorAcaoMixin, viewsets.ModelViewSet):
    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated]

    permissoes_por_acao = {
        'create': [IsAtendente],
        'update': [IsAtendente],
        'partial_update': [IsAtendente],
        'destroy': [IsAtendente],
    }

    def get_queryset(self):
        queryset = Cliente.objects.all().order_by('-created_at')
        if not self.request.user.is_operador:
            # CPF/CNPJ é dado pessoal: cliente com login só vê o próprio cadastro.
            return queryset.filter(usuario=self.request.user)
        return self._filtrar_por_documento(queryset)

    def _filtrar_por_documento(self, queryset):
        """Comando Identificar cliente por CPF/CNPJ: ?cpf_cnpj=529.982.247-25.

        Compara só os dígitos, então encontra o cliente com ou sem pontuação.
        """
        informado = self.request.query_params.get('cpf_cnpj')
        if not informado:
            return queryset

        digitos = re.sub(r'\D', '', informado)
        if not digitos:
            return queryset.none()

        return queryset.annotate(
            documento=Replace(
                Replace(
                    Replace('cpf_cnpj', Value('.'), Value('')),
                    Value('-'), Value(''),
                ),
                Value('/'), Value(''),
            ),
        ).filter(documento=digitos)
