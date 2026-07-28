from rest_framework import serializers

from so.models import ItemServicoOS


class ItemServicoOSSerializer(serializers.ModelSerializer):
    servico_nome = serializers.CharField(source='servico.nome', read_only=True)
    subtotal = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = ItemServicoOS
        fields = [
            'id',
            'uuid',
            'ordem_servico',
            'servico',
            'servico_nome',
            'orcamento',
            'quantidade',
            'preco_unitario',
            'subtotal',
            'created_at',
        ]
        # preco_unitario é congelado a partir do catálogo na inclusão.
        read_only_fields = ['id', 'uuid', 'orcamento', 'preco_unitario', 'created_at']

    def create(self, validated_data):
        validated_data['preco_unitario'] = validated_data['servico'].preco
        return super().create(validated_data)
