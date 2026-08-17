from rest_framework import viewsets

from accounts.permissions import (
    IsAtendente,
    IsMecanico,
    IsOperador,
    PermissoesPorAcaoMixin,
    has_any_role,
)
from so.models import ItemServicoOS
from so.serializers import ItemServicoOSSerializer


class ItemServicoOSViewSet(PermissoesPorAcaoMixin, viewsets.ModelViewSet):
    queryset = ItemServicoOS.objects.select_related(
        'ordem_servico',
        'servico',
    ).order_by('-created_at')
    serializer_class = ItemServicoOSSerializer
    permission_classes = [IsOperador]

    # Serviço é item de catálogo e não mexe em estoque, então o atendente
    # também inclui: é ele quem atende o cliente que pede um serviço a mais.
    # Peça continua só com o mecânico, em ItemPecaOSViewSet.
    _INCLUIR = [has_any_role(IsMecanico, IsAtendente)]
    permissoes_por_acao = {
        'create': _INCLUIR,
        'update': _INCLUIR,
        'partial_update': _INCLUIR,
        'destroy': _INCLUIR,
    }
