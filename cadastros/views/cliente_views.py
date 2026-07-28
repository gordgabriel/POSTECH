from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from cadastros.models import Cliente
from cadastros.serializers import ClienteSerializer


class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.all().order_by('-created_at')
    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated]
