from rest_framework import serializers

from cadastros.models import Servico
from cadastros.validators import validar_cpf_cnpj, validar_placa
from estoque.models import Peca
from oficina.atendimento.dominio.ordem_servico import veiculo_pertence_ao_cliente
from so.models import OrdemServico
from so.serializers.item_peca_serializer import ItemPecaOSSerializer
from so.serializers.item_servico_serializer import ItemServicoOSSerializer
from so.serializers.orcamento_serializer import OrcamentoSerializer


class OrdemServicoSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source='cliente.nome', read_only=True)
    veiculo_placa = serializers.CharField(source='veiculo.placa', read_only=True)
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
        # Status e diagnóstico mudam pelos comandos de negócio, não por PATCH.
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
        if veiculo and cliente and not veiculo_pertence_ao_cliente(
            veiculo.cliente_id, cliente.pk,
        ):
            raise serializers.ValidationError(
                {'veiculo': 'O veículo informado não pertence ao cliente da OS.'},
            )
        return attrs

    def create(self, validated_data):
        from So_PosTech.container import atendimento

        return atendimento().criar_os.executar(validated_data)


class StatusOSSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    atualizada_em = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = OrdemServico
        fields = ['id', 'uuid', 'status', 'status_display', 'atualizada_em']
        read_only_fields = fields


class _ClienteDaAbertura(serializers.Serializer):
    cpf_cnpj = serializers.CharField(max_length=18, validators=[validar_cpf_cnpj])
    nome = serializers.CharField(max_length=100, required=False)
    email = serializers.EmailField(max_length=254, required=False)
    telefone = serializers.CharField(max_length=15, required=False)


class _VeiculoDaAbertura(serializers.Serializer):
    placa = serializers.CharField(max_length=8, validators=[validar_placa])
    marca = serializers.CharField(max_length=255, required=False)
    modelo = serializers.CharField(max_length=255, required=False)
    ano = serializers.IntegerField(required=False)


class _ServicoDaAbertura(serializers.Serializer):
    servico = serializers.PrimaryKeyRelatedField(queryset=Servico.objects.filter(ativo=True))
    quantidade = serializers.IntegerField(min_value=1, default=1)


class _PecaDaAbertura(serializers.Serializer):
    peca = serializers.PrimaryKeyRelatedField(queryset=Peca.objects.all())
    quantidade = serializers.IntegerField(min_value=1, default=1)


class AberturaOSSerializer(serializers.Serializer):
    cliente = _ClienteDaAbertura()
    veiculo = _VeiculoDaAbertura()
    descricao = serializers.CharField()
    observacoes = serializers.CharField(required=False, allow_blank=True)
    servicos = _ServicoDaAbertura(many=True, required=False, default=list)
    pecas = _PecaDaAbertura(many=True, required=False, default=list)
