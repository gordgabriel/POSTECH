from django.db.models import Q
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from so.models import OSModel
from so.serializers import OSSerializer


class OSViewSet(viewsets.ModelViewSet):
    serializer_class = OSSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = OSModel.objects.select_related(
            'user',
            'responsible',
        ).order_by('-created_at')
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(
            Q(user=self.request.user) | Q(responsible=self.request.user),
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
