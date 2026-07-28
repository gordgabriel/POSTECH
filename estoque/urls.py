from django.urls import include, path
from rest_framework.routers import DefaultRouter

from estoque.views import PecaViewSet

router = DefaultRouter()
router.register('pecas', PecaViewSet, basename='peca')

urlpatterns = [
    path('', include(router.urls)),
]
