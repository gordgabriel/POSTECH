from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsAtendente, PermissoesPorAcaoMixin
from cadastros.models import Veiculo
from cadastros.serializers import VeiculoSerializer


class VeiculoViewSet(PermissoesPorAcaoMixin, viewsets.ModelViewSet):
    serializer_class = VeiculoSerializer
    permission_classes = [IsAuthenticated]

    permissoes_por_acao = {
        'create': [IsAtendente],
        'update': [IsAtendente],
        'partial_update': [IsAtendente],
        'destroy': [IsAtendente],
    }

    def get_queryset(self):
        queryset = Veiculo.objects.select_related('cliente').order_by('-created_at')
        if self.request.user.is_operador:
            return queryset
        return queryset.filter(cliente__usuario=self.request.user)
