from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from so.models import ItemPecaOS


class ItemPecaOSSerializer(serializers.ModelSerializer):
    peca_nome = serializers.CharField(source='peca.nome', read_only=True)
    subtotal = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = ItemPecaOS
        fields = [
            'id',
            'uuid',
            'ordem_servico',
            'peca',
            'peca_nome',
            'orcamento',
            'quantidade',
            'preco_unitario',
            'subtotal',
            'created_at',
        ]
        # preco_unitario é congelado a partir do catálogo na inclusão.
        read_only_fields = ['id', 'uuid', 'orcamento', 'preco_unitario', 'created_at']

    def create(self, validated_data):
        validated_data['preco_unitario'] = validated_data['peca'].preco
        try:
            return super().create(validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'quantidade': exc.messages})
