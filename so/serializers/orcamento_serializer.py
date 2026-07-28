from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from so.models import Orcamento
from so.serializers.item_peca_serializer import ItemPecaOSSerializer
from so.serializers.item_servico_serializer import ItemServicoOSSerializer


class OrcamentoSerializer(serializers.ModelSerializer):
    itens_servico = ItemServicoOSSerializer(many=True, read_only=True)
    itens_peca = ItemPecaOSSerializer(many=True, read_only=True)

    class Meta:
        model = Orcamento
        fields = [
            'id',
            'uuid',
            'ordem_servico',
            'sequencia',
            'valor_total',
            'status',
            'data_geracao',
            'data_envio',
            'data_resposta',
            'itens_servico',
            'itens_peca',
        ]
        # Gerado a partir dos itens da OS: nada além da OS é escrito na criação.
        read_only_fields = [
            'id',
            'uuid',
            'sequencia',
            'valor_total',
            'status',
            'data_geracao',
            'data_envio',
            'data_resposta',
        ]

    def create(self, validated_data):
        try:
            return Orcamento.gerar_para_os(validated_data['ordem_servico'])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
