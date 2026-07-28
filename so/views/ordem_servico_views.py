from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from so.models import OrdemServico
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
