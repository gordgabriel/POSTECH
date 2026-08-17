from datetime import timedelta

from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_naive, make_aware
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsOperador
from so.models import OrdemServico


class TempoMedioExecucaoView(APIView):
    """
    Tempo médio entre data_inicio_execucao e data_finalizacao das OS concluídas.
    Filtros opcionais: ?de=2026-01-01T00:00:00&ate=2026-12-31T23:59:59
    """

    permission_classes = [IsOperador]

    @staticmethod
    def _parse(valor):
        """Filtro sem fuso é interpretado no fuso do projeto."""
        data = parse_datetime(valor or '')
        if data and is_naive(data):
            return make_aware(data)
        return data

    def get(self, request):
        queryset = OrdemServico.objects.filter(
            data_inicio_execucao__isnull=False,
            data_finalizacao__isnull=False,
        )

        de = self._parse(request.query_params.get('de', ''))
        ate = self._parse(request.query_params.get('ate', ''))
        if de:
            queryset = queryset.filter(data_finalizacao__gte=de)
        if ate:
            queryset = queryset.filter(data_finalizacao__lte=ate)

        duracoes = []
        for os_ in queryset:
            delta = os_.data_finalizacao - os_.data_inicio_execucao
            duracoes.append(delta.total_seconds())

        total = len(duracoes)
        if total == 0:
            return Response({
                'total_os': 0,
                'tempo_medio_minutos': None,
                'tempo_medio_horas': None,
            })

        media_segundos = sum(duracoes) / total
        media = timedelta(seconds=media_segundos)

        return Response({
            'total_os': total,
            'tempo_medio_minutos': round(media.total_seconds() / 60, 2),
            'tempo_medio_horas': round(media.total_seconds() / 3600, 2),
        })
