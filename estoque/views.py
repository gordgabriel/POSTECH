from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import PecaEstoque
from .serializers import PecaEstoqueSerializer


class PecaEstoqueViewSet(viewsets.ModelViewSet):
    queryset = PecaEstoque.objects.all().order_by('-created_at')
    serializer_class = PecaEstoqueSerializer
    permission_classes = [IsAuthenticated]
