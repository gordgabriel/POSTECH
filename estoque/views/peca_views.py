from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import IsEstoquista, IsOperador, PermissoesPorAcaoMixin
from estoque.models import Peca
from estoque.serializers import PecaSerializer


class PecaViewSet(PermissoesPorAcaoMixin, viewsets.ModelViewSet):
    queryset = Peca.objects.all().order_by('nome')
    serializer_class = PecaSerializer
    # Saldo de estoque é informação interna: o cliente não consulta.
    permission_classes = [IsOperador]

    permissoes_por_acao = {
        'create': [IsEstoquista],
        'update': [IsEstoquista],
        'partial_update': [IsEstoquista],
        'destroy': [IsEstoquista],
    }

    @action(detail=False, methods=['get'])
    def alertas(self, request):
        """Peças com estoque disponível abaixo do mínimo configurado."""
        alertas = [p for p in self.get_queryset() if p.abaixo_do_minimo]
        serializer = self.get_serializer(alertas, many=True)
        return Response(serializer.data)
