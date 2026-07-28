from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from so.models import ItemServicoOS
from so.serializers import ItemServicoOSSerializer


class ItemServicoOSViewSet(viewsets.ModelViewSet):
    queryset = ItemServicoOS.objects.select_related(
        'ordem_servico',
        'servico',
    ).order_by('-created_at')
    serializer_class = ItemServicoOSSerializer
    permission_classes = [IsAuthenticated]
