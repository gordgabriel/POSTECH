from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from cadastros.models import Servico
from cadastros.serializers import ServicoSerializer


class ServicoViewSet(viewsets.ModelViewSet):
    queryset = Servico.objects.all().order_by('nome')
    serializer_class = ServicoSerializer
    permission_classes = [IsAuthenticated]
