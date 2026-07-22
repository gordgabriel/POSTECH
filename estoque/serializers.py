from rest_framework import serializers

from .models import PecaEstoque


class PecaEstoqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = PecaEstoque
        fields = ['id', 'nome', 'quantidade', 'descricao', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
