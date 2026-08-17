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
from so.models import OrdemServico, StatusOS
from so.serializers import OrdemServicoSerializer


class OrdemServicoViewSet(PermissoesPorAcaoMixin, viewsets.ModelViewSet):
    serializer_class = OrdemServicoSerializer
    permission_classes = [IsAuthenticated]

    # Cada comando pertence ao ator que o executa na oficina. Listar e detalhar
    # ficam abertos: o get_queryset limita o cliente às próprias OS.
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
            OrdemServico.objects.select_related('cliente', 'veiculo', 'responsavel')
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
        """Modelo de leitura Histórico do cliente e do veículo.

        ?cliente= e ?veiculo= aceitam id ou uuid, porque o serializer expõe os
        dois. Valor que não é nenhum dos dois devolve lista vazia, não erro: é
        consulta, e consulta que não acha nada não achou nada.
        """
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

    def _transitar(self, ordem_servico, novo_status):
        """Traduz o comando HTTP em transição de domínio; o erro vira 400."""
        try:
            ordem_servico.transitar_para(novo_status)
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
        diagnostico = (request.data.get('diagnostico') or '').strip()
        if not diagnostico:
            return Response(
                {'diagnostico': ['Informe o parecer do diagnóstico.']},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        ordem_servico.diagnostico = diagnostico
        if ordem_servico.status == StatusOS.EM_DIAGNOSTICO:
            # Revisão do parecer: não há transição a fazer.
            ordem_servico.save(update_fields=['diagnostico', 'updated_at'])
            return Response(self.get_serializer(ordem_servico).data)
        # transitar_para grava o diagnóstico junto; transição inválida não grava nada.
        return self._transitar(ordem_servico, StatusOS.EM_DIAGNOSTICO)

    @action(detail=True, methods=['post'])
    def finalizar(self, request, pk=None):
        """Comando Finalizar OS -> status Finalizada."""
        return self._transitar(self.get_object(), StatusOS.FINALIZADA)

    @action(detail=True, methods=['post'])
    def entregar(self, request, pk=None):
        """Comando Registrar entrega do veículo -> Entregue + baixa de estoque."""
        return self._transitar(self.get_object(), StatusOS.ENTREGUE)

    @action(detail=True, methods=['post'])
    def encerrar(self, request, pk=None):
        """Comando Encerrar OS: baixa o registro e libera as reservas."""
        ordem_servico = self.get_object()
        try:
            ordem_servico.encerrar()
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(ordem_servico).data)
