from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts.views import HealthCheckView, ProfileView, UserViewSet, VehicleViewSet

router = DefaultRouter()
router.register('users', UserViewSet, basename='user')
router.register('vehicles', VehicleViewSet, basename='vehicle')

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='health'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('', include(router.urls)),
]
