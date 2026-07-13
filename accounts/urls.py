from django.urls import path

from .views import HealthCheckView, ProfileView

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='health'),
    path('profile/', ProfileView.as_view(), name='profile'),
]
