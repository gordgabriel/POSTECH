from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import PecaEstoque
from .serializers import PecaEstoqueSerializer


class PecaEstoqueViewSet(viewsets.ModelViewSet):
    queryset = PecaEstoque.objects.all().order_by('-created_at')
    serializer_class = PecaEstoqueSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['post'], url_path='reservar')
    def reservar(self, request, pk=None):
        peca = self.get_object()
        # validação: não pode reservar mais que o disponível
        if peca.quantidade_reservada + 1 > peca.quantidade:
            return Response(
                {'detail': 'Quantidade reservada não pode ser maior que a quantidade disponível.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        peca.quantidade_reservada += 1
        peca.save()
        serializer = self.get_serializer(peca)
        return Response(serializer.data, status=status.HTTP_200_OK)
