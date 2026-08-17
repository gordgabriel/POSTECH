from rest_framework import viewsets

from accounts.permissions import IsMecanico, IsOperador, PermissoesPorAcaoMixin
from so.models import ItemServicoOS
from so.serializers import ItemServicoOSSerializer


class ItemServicoOSViewSet(PermissoesPorAcaoMixin, viewsets.ModelViewSet):
    queryset = ItemServicoOS.objects.select_related(
        'ordem_servico',
        'servico',
    ).order_by('-created_at')
    serializer_class = ItemServicoOSSerializer
    permission_classes = [IsOperador]

    # Quem monta a lista de reparos é o mecânico. O cliente vê os itens
    # aninhados na própria OS, não por esta rota.
    permissoes_por_acao = {
        'create': [IsMecanico],
        'update': [IsMecanico],
        'partial_update': [IsMecanico],
        'destroy': [IsMecanico],
    }
