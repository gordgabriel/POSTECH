from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from so.models import Orcamento
from so.serializers import OrcamentoSerializer


class OrcamentoViewSet(viewsets.ModelViewSet):
    queryset = (
        Orcamento.objects.select_related('ordem_servico')
        .prefetch_related('itens_servico', 'itens_peca')
        .order_by('-data_geracao')
    )
    serializer_class = OrcamentoSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_operador:
            return queryset
        return queryset.filter(ordem_servico__cliente__usuario=self.request.user)

    def _responder(self, aprovado):
        orcamento = self.get_object()
        try:
            orcamento.responder(aprovado=aprovado)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(orcamento).data)

    @action(detail=True, methods=['post'])
    def enviar(self, request, pk=None):
        """Comando Enviar orçamento ao cliente -> OS Aguardando aprovação."""
        orcamento = self.get_object()
        try:
            orcamento.enviar()
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(orcamento).data)

    @action(detail=True, methods=['post'])
    def aprovar(self, request, pk=None):
        return self._responder(aprovado=True)

    @action(detail=True, methods=['post'])
    def recusar(self, request, pk=None):
        return self._responder(aprovado=False)
