import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Case, IntegerField, Value, When
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework import status as http_status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import (
    IsAdmin,
    IsAtendente,
    IsMecanico,
    PermissoesPorAcaoMixin,
)
from oficina.atendimento.dominio.erros import ParecerObrigatorio
from oficina.atendimento.dominio.ordem_servico import (
    FORA_DA_LISTAGEM,
    PRIORIDADE_NA_LISTAGEM,
)
from So_PosTech.container import atendimento
from So_PosTech.exceptions import traduzir_erros_de_dominio
from so.models import OrdemServico
from so.serializers import (
    AberturaOSSerializer,
    OrdemServicoSerializer,
    StatusOSSerializer,
)


def _identificador(valor):
    if valor.isdigit():
        return 'id', int(valor)
    try:
        return 'uuid', uuid.UUID(valor)
    except ValueError:
        return None


class OrdemServicoViewSet(PermissoesPorAcaoMixin, viewsets.ModelViewSet):
    serializer_class = OrdemServicoSerializer
    permission_classes = [IsAuthenticated]

    permissoes_por_acao = {
        'create': [IsAtendente],
        'abrir': [IsAtendente],
        'update': [IsAtendente],
        'partial_update': [IsAtendente],
        'destroy': [IsAdmin],
        'diagnosticar': [IsMecanico],
        'finalizar': [IsMecanico],
        'entregar': [IsAtendente],
        'encerrar': [IsAtendente],
    }

    def get_queryset(self):
        queryset = (
            OrdemServico.objects.select_related('cliente', 'veiculo')
            .prefetch_related('itens_servico', 'itens_peca', 'orcamentos')
            .order_by('-data_abertura')
        )
        if not self.request.user.is_operador:
            # Cliente com login só enxerga as próprias OS.
            queryset = queryset.filter(cliente__usuario=self.request.user)
        queryset = self._filtrar_por_atividade(queryset)
        return self._ordenar_por_prioridade(self._filtrar_por_historico(queryset))

    def _filtrar_por_atividade(self, queryset):
        """Padrão: OS em andamento; false e todas trazem o histórico."""
        if self.action != 'list':
            return queryset

        informado = (self.request.query_params.get('is_active') or 'true').lower()
        if informado in ('todas', 'all'):
            return queryset
        if informado in ('false', '0'):
            return queryset.filter(is_active=False)
        return queryset.filter(is_active=True).exclude(
            status__in=[status.value for status in FORA_DA_LISTAGEM],
        )

    def _ordenar_por_prioridade(self, queryset):
        if self.action != 'list':
            return queryset

        prioridade = Case(
            *(
                When(status=status.value, then=Value(posicao))
                for posicao, status in enumerate(PRIORIDADE_NA_LISTAGEM)
            ),
            default=Value(len(PRIORIDADE_NA_LISTAGEM)),
            output_field=IntegerField(),
        )
        return queryset.alias(prioridade=prioridade).order_by(
            'prioridade', 'data_abertura', 'id',
        )

    def _filtrar_por_historico(self, queryset):
        # ?cliente= e ?veiculo= aceitam id ou uuid.
        if self.action != 'list':
            return queryset

        for parametro, campo in (('cliente', 'cliente'), ('veiculo', 'veiculo')):
            informado = self.request.query_params.get(parametro)
            if not informado:
                continue
            chave = _identificador(informado)
            if chave is None:
                return queryset.none()
            tipo, valor = chave
            queryset = queryset.filter(**{f'{campo}__{tipo}': valor})
        return queryset

    def _comando(self, ordem_servico, executar, exceto=()):
        """Executa o caso de uso sobre a OS; erro de domínio vira 400."""
        try:
            with traduzir_erros_de_dominio(exceto):
                executar(atendimento(ordem_servico))
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(ordem_servico).data)

    @extend_schema(responses={201: OrdemServicoSerializer})
    @action(detail=False, methods=['post'], serializer_class=AberturaOSSerializer)
    def abrir(self, request):
        """Abre a OS com cliente, veículo, serviços e peças."""
        entrada = self.get_serializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        dados = entrada.validated_data
        try:
            with traduzir_erros_de_dominio():
                ordem_servico = atendimento().abrir_os.executar(
                    cliente=dict(dados['cliente']),
                    veiculo=dict(dados['veiculo']),
                    descricao=dados['descricao'],
                    observacoes=dados.get('observacoes'),
                    servicos=[(i['servico'].pk, i['quantidade']) for i in dados['servicos']],
                    pecas=[(i['peca'].pk, i['quantidade']) for i in dados['pecas']],
                )
        except DjangoValidationError as exc:
            erros = exc.message_dict if hasattr(exc, 'error_dict') else exc.messages
            raise serializers.ValidationError(erros) from exc
        return Response(
            OrdemServicoSerializer(ordem_servico).data,
            status=http_status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'], serializer_class=StatusOSSerializer)
    def status(self, request, pk=None):
        """Status da OS, por id ou uuid."""
        chave = _identificador(pk)
        if chave is None:
            raise Http404
        tipo, valor = chave
        ordem_servico = get_object_or_404(self.get_queryset(), **{tipo: valor})
        self.check_object_permissions(request, ordem_servico)
        return Response(self.get_serializer(ordem_servico).data)

    @action(detail=True, methods=['post'])
    def diagnosticar(self, request, pk=None):
        """Comando Realizar diagnóstico -> status Em diagnóstico."""
        ordem_servico = self.get_object()
        parecer = request.data.get('diagnostico')
        try:
            return self._comando(
                ordem_servico,
                lambda casos: casos.realizar_diagnostico.executar(ordem_servico.pk, parecer),
                exceto=ParecerObrigatorio,
            )
        except ParecerObrigatorio as exc:
            return Response(
                {exc.campo: [exc.mensagem]},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=['post'])
    def finalizar(self, request, pk=None):
        """Comando Finalizar OS -> status Finalizada."""
        ordem_servico = self.get_object()
        return self._comando(
            ordem_servico,
            lambda casos: casos.finalizar_os.executar(ordem_servico.pk),
        )

    @action(detail=True, methods=['post'])
    def entregar(self, request, pk=None):
        """Comando Registrar entrega do veículo -> Entregue + baixa de estoque."""
        ordem_servico = self.get_object()
        return self._comando(
            ordem_servico,
            lambda casos: casos.registrar_entrega.executar(ordem_servico.pk),
        )

    @action(detail=True, methods=['post'])
    def encerrar(self, request, pk=None):
        """Comando Encerrar OS: baixa o registro e libera as reservas."""
        ordem_servico = self.get_object()
        return self._comando(
            ordem_servico,
            lambda casos: casos.encerrar_os.executar(ordem_servico.pk),
        )
