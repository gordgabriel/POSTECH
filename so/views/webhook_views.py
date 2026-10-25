from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import TokenDeWebhook
from so.models import Orcamento
from so.serializers import OrcamentoSerializer, RespostaExternaSerializer
from so.views.orcamento_views import executar_resposta


class RespostaOrcamentoWebhookView(APIView):
    authentication_classes = []
    permission_classes = [TokenDeWebhook]

    @extend_schema(
        request=RespostaExternaSerializer,
        responses=OrcamentoSerializer,
        auth=[],
        parameters=[
            OpenApiParameter(
                'X-Webhook-Token',
                OpenApiTypes.STR,
                OpenApiParameter.HEADER,
                required=True,
                description='Token compartilhado (variável WEBHOOK_TOKEN).',
            ),
        ],
        description=(
            'Reenviar a mesma decisão devolve 200 sem repetir efeitos; '
            'decisão contrária à já registrada devolve 409.'
        ),
    )
    def post(self, request):
        entrada = RespostaExternaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        orcamento = get_object_or_404(Orcamento, uuid=entrada.validated_data['orcamento'])
        aprovado = entrada.validated_data['aprovado']

        erro = executar_resposta(
            orcamento,
            lambda casos: casos.receber_resposta_externa.executar(orcamento.pk, aprovado),
        )
        if erro is not None:
            return erro
        return Response(OrcamentoSerializer(orcamento).data)
