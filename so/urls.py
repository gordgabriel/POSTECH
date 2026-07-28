from django.urls import include, path
from rest_framework.routers import DefaultRouter

from so.views import (
    ItemPecaOSViewSet,
    ItemServicoOSViewSet,
    OrcamentoViewSet,
    OrdemServicoViewSet,
    TempoMedioExecucaoView,
)

router = DefaultRouter()
router.register('ordens-servico', OrdemServicoViewSet, basename='ordem-servico')
router.register('itens-servico', ItemServicoOSViewSet, basename='item-servico')
router.register('itens-peca', ItemPecaOSViewSet, basename='item-peca')
router.register('orcamentos', OrcamentoViewSet, basename='orcamento')

urlpatterns = [
    path(
        'relatorios/tempo-medio-execucao/',
        TempoMedioExecucaoView.as_view(),
        name='tempo-medio-execucao',
    ),
    path('', include(router.urls)),
]