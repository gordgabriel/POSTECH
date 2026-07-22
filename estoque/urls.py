from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PecaEstoqueViewSet

router = DefaultRouter()
router.register('pecas', PecaEstoqueViewSet, basename='peca-estoque')

urlpatterns = [
    path('', include(router.urls)),
]
