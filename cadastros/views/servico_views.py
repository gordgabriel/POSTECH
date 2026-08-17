from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsAdmin, PermissoesPorAcaoMixin
from cadastros.models import Servico
from cadastros.serializers import ServicoSerializer


class ServicoViewSet(PermissoesPorAcaoMixin, viewsets.ModelViewSet):
    queryset = Servico.objects.all().order_by('nome')
    serializer_class = ServicoSerializer
    # O catálogo é consultado por todos, inclusive pelo cliente que recebe o
    # orçamento; mexer no preço de tabela é decisão administrativa.
    permission_classes = [IsAuthenticated]

    permissoes_por_acao = {
        'create': [IsAdmin],
        'update': [IsAdmin],
        'partial_update': [IsAdmin],
        'destroy': [IsAdmin],
    }
