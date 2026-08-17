from rest_framework import serializers

from so.models import OrdemServico
from so.serializers.item_peca_serializer import ItemPecaOSSerializer
from so.serializers.item_servico_serializer import ItemServicoOSSerializer
from so.serializers.orcamento_serializer import OrcamentoSerializer


class OrdemServicoSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source='cliente.nome', read_only=True)
    veiculo_placa = serializers.CharField(source='veiculo.placa', read_only=True)
    responsavel_username = serializers.CharField(
        source='responsavel.username',
        read_only=True,
        default=None,
    )
    itens_servico = ItemServicoOSSerializer(many=True, read_only=True)
    itens_peca = ItemPecaOSSerializer(many=True, read_only=True)
    orcamentos = OrcamentoSerializer(many=True, read_only=True)

    class Meta:
        model = OrdemServico
        fields = [
            'id',
            'uuid',
            'descricao',
            'diagnostico',
            'observacoes',
            'status',
            'cliente',
            'cliente_nome',
            'veiculo',
            'veiculo_placa',
            'responsavel',
            'responsavel_username',
            'data_abertura',
            'data_diagnostico',
            'data_inicio_execucao',
            'data_finalizacao',
            'data_entrega',
            'is_active',
            'itens_servico',
            'itens_peca',
            'orcamentos',
            'updated_at',
        ]
        # O status e o diagnóstico não são campos de escrita: mudam como
        # consequência dos comandos de negócio (/diagnosticar/, /finalizar/,
        # /entregar/, /cancelar/ e o /enviar/ e /aprovar/ do orçamento).
        read_only_fields = [
            'id',
            'uuid',
            'status',
            'diagnostico',
            'data_abertura',
            'data_diagnostico',
            'data_inicio_execucao',
            'data_finalizacao',
            'data_entrega',
            'updated_at',
        ]

    def validate(self, attrs):
        veiculo = attrs.get('veiculo') or (self.instance and self.instance.veiculo)
        cliente = attrs.get('cliente') or (self.instance and self.instance.cliente)
        if veiculo and cliente and veiculo.cliente_id != cliente.pk:
            raise serializers.ValidationError(
                {'veiculo': 'O veículo informado não pertence ao cliente da OS.'},
            )
        return attrs
