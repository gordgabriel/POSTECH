from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from So_PosTech.exceptions import traduzir_erros_de_dominio
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
        from So_PosTech.container import atendimento

        ordem_servico = validated_data['ordem_servico']
        casos = atendimento(ordem_servico)
        try:
            with traduzir_erros_de_dominio():
                orcamento = casos.gerar_orcamento.executar(ordem_servico.pk)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return casos.orcamentos.modelo(orcamento.id)
