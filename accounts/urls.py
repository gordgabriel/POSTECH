from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts.views import HealthCheckView, ProfileView, UserViewSet

router = DefaultRouter()
router.register('users', UserViewSet, basename='user')

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='health'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('', include(router.urls)),
]
