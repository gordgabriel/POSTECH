from django.urls import include, path
from rest_framework.routers import DefaultRouter

from cadastros.views import ClienteViewSet, ServicoViewSet, VeiculoViewSet

router = DefaultRouter()
router.register('clientes', ClienteViewSet, basename='cliente')
router.register('veiculos', VeiculoViewSet, basename='veiculo')
router.register('servicos', ServicoViewSet, basename='servico')

urlpatterns = [
    path('', include(router.urls)),
]
