from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from cadastros.models import Veiculo
from cadastros.serializers import VeiculoSerializer


class VeiculoViewSet(viewsets.ModelViewSet):
    queryset = Veiculo.objects.select_related('cliente').order_by('-created_at')
    serializer_class = VeiculoSerializer
    permission_classes = [IsAuthenticated]
