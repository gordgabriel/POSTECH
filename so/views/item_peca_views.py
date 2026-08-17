from rest_framework import viewsets

from accounts.permissions import IsMecanico, IsOperador, PermissoesPorAcaoMixin
from so.models import ItemPecaOS
from so.serializers import ItemPecaOSSerializer


class ItemPecaOSViewSet(PermissoesPorAcaoMixin, viewsets.ModelViewSet):
    queryset = ItemPecaOS.objects.select_related(
        'ordem_servico',
        'peca',
    ).order_by('-created_at')
    serializer_class = ItemPecaOSSerializer
    permission_classes = [IsOperador]

    permissoes_por_acao = {
        'create': [IsMecanico],
        'update': [IsMecanico],
        'partial_update': [IsMecanico],
        'destroy': [IsMecanico],
    }
