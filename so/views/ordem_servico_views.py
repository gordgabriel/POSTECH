import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
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
from So_PosTech.container import atendimento
from So_PosTech.exceptions import traduzir_erros_de_dominio
from so.models import OrdemServico
from so.serializers import OrdemServicoSerializer


class OrdemServicoViewSet(PermissoesPorAcaoMixin, viewsets.ModelViewSet):
    serializer_class = OrdemServicoSerializer
    permission_classes = [IsAuthenticated]

    permissoes_por_acao = {
        'create': [IsAtendente],
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
        return self._filtrar_por_historico(self._filtrar_por_atividade(queryset))

    def _filtrar_por_atividade(self, queryset):
        """OS encerrada sai de circulação; ?is_active=false traz o histórico."""
        if self.action != 'list':
            return queryset

        informado = self.request.query_params.get('is_active')
        if informado is None:
            return queryset.filter(is_active=True)
        if informado.lower() in ('todas', 'all'):
            return queryset
        return queryset.filter(is_active=informado.lower() not in ('false', '0'))

    def _filtrar_por_historico(self, queryset):
        # ?cliente= e ?veiculo= aceitam id ou uuid.
        if self.action != 'list':
            return queryset

        for parametro, campo in (('cliente', 'cliente'), ('veiculo', 'veiculo')):
            informado = self.request.query_params.get(parametro)
            if not informado:
                continue
            if informado.isdigit():
                queryset = queryset.filter(**{f'{campo}_id': int(informado)})
            else:
                try:
                    uuid.UUID(informado)
                except ValueError:
                    return queryset.none()
                queryset = queryset.filter(**{f'{campo}__uuid': informado})
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
