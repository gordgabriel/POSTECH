from rest_framework import serializers

from cadastros.models import Cliente


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = [
            'id',
            'uuid',
            'cpf_cnpj',
            'nome',
            'email',
            'telefone',
            'data_nascimento',
            'endereco',
            'usuario',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'uuid', 'created_at', 'updated_at']
