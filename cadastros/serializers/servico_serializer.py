from rest_framework import serializers

from cadastros.models import Servico


class ServicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servico
        fields = [
            'id',
            'uuid',
            'nome',
            'descricao',
            'preco',
            'tempo_execucao',
            'ativo',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'uuid', 'created_at', 'updated_at']
