from rest_framework import serializers

from cadastros.models import Veiculo


class VeiculoSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source='cliente.nome', read_only=True)

    class Meta:
        model = Veiculo
        fields = [
            'id',
            'uuid',
            'placa',
            'marca',
            'modelo',
            'ano',
            'observacao',
            'cliente',
            'cliente_nome',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'uuid', 'created_at', 'updated_at']

    def validate_placa(self, value):
        return value.upper().replace('-', '')
