from rest_framework import serializers

from estoque.models import Peca


class PecaSerializer(serializers.ModelSerializer):
    quantidade_disponivel = serializers.IntegerField(read_only=True)
    abaixo_do_minimo = serializers.BooleanField(read_only=True)

    class Meta:
        model = Peca
        fields = [
            'id',
            'uuid',
            'nome',
            'descricao',
            'preco',
            'quantidade',
            'quantidade_reservada',
            'estoque_minimo',
            'quantidade_disponivel',
            'abaixo_do_minimo',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'uuid', 'created_at', 'updated_at']
