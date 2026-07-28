from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from so.models import ItemPecaOS
from so.serializers import ItemPecaOSSerializer


class ItemPecaOSViewSet(viewsets.ModelViewSet):
    queryset = ItemPecaOS.objects.select_related(
        'ordem_servico',
        'peca',
    ).order_by('-created_at')
    serializer_class = ItemPecaOSSerializer
    permission_classes = [IsAuthenticated]
