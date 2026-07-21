from django.urls import include, path
from rest_framework.routers import DefaultRouter

from so.views import OSViewSet

router = DefaultRouter()
router.register('service-orders', OSViewSet, basename='service-order')

urlpatterns = [
    path('', include(router.urls)),
]
