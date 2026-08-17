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
        if self.request.user.is_operador:
            return queryset
        # CPF/CNPJ é dado pessoal: cliente com login só enxerga o próprio cadastro.
        return queryset.filter(usuario=self.request.user)
