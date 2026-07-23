from rest_framework import serializers

from .models import PecaEstoque


class PecaEstoqueSerializer(serializers.ModelSerializer):
    def validate(self, data):
        quantidade = data.get('quantidade', getattr(self.instance, 'quantidade', None))
        quantidade_reservada = data.get('quantidade_reservada', getattr(self.instance, 'quantidade_reservada', None))
        if quantidade is not None and quantidade_reservada is not None:
            if quantidade_reservada > quantidade:
                raise serializers.ValidationError({
                    'quantidade_reservada': 'Quantidade reservada não pode ser maior que a quantidade disponível.'
                })
        return data
    class Meta:
        model = PecaEstoque
        fields = ['id', 'nome', 'quantidade', 'quantidade_reservada', 'descricao', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
        
