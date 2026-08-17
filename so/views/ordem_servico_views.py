from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status as http_status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from so.models import OrdemServico, StatusOS
from so.serializers import OrdemServicoSerializer


class OrdemServicoViewSet(viewsets.ModelViewSet):
    serializer_class = OrdemServicoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            OrdemServico.objects.select_related('cliente', 'veiculo', 'responsavel')
            .prefetch_related('itens_servico', 'itens_peca', 'orcamentos')
            .order_by('-data_abertura')
        )
        if self.request.user.is_operador:
            return queryset
        # Cliente com login só enxerga as próprias OS.
        return queryset.filter(cliente__usuario=self.request.user)

    def _transitar(self, ordem_servico, novo_status):
        """Traduz o comando HTTP em transição de domínio; o erro vira 400."""
        try:
            ordem_servico.transitar_para(novo_status)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(ordem_servico).data)

    @action(detail=True, methods=['post'])
    def diagnosticar(self, request, pk=None):
        """Comando Realizar diagnóstico -> status Em diagnóstico."""
        ordem_servico = self.get_object()
        diagnostico = (request.data.get('diagnostico') or '').strip()
        if not diagnostico:
            return Response(
                {'diagnostico': ['Informe o parecer do diagnóstico.']},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        ordem_servico.diagnostico = diagnostico
        if ordem_servico.status == StatusOS.EM_DIAGNOSTICO:
            # Revisão do parecer: não há transição a fazer.
            ordem_servico.save(update_fields=['diagnostico', 'updated_at'])
            return Response(self.get_serializer(ordem_servico).data)
        # transitar_para grava o diagnóstico junto; transição inválida não grava nada.
        return self._transitar(ordem_servico, StatusOS.EM_DIAGNOSTICO)

    @action(detail=True, methods=['post'])
    def finalizar(self, request, pk=None):
        """Comando Finalizar OS -> status Finalizada."""
        return self._transitar(self.get_object(), StatusOS.FINALIZADA)

    @action(detail=True, methods=['post'])
    def entregar(self, request, pk=None):
        """Comando Registrar entrega do veículo -> Entregue + baixa de estoque."""
        return self._transitar(self.get_object(), StatusOS.ENTREGUE)

    @action(detail=True, methods=['post'])
    def cancelar(self, request, pk=None):
        """Comando Cancelar OS -> Cancelada + liberação das reservas."""
        return self._transitar(self.get_object(), StatusOS.CANCELADA)
