from rest_framework import serializers

from accounts.models import VehiclesModel


class VehicleSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = VehiclesModel
        fields = [
            'id',
            'uuid',
            'brand',
            'model',
            'year',
            'plate',
            'annotation',
            'user',
            'user_username',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'uuid', 'user', 'created_at', 'updated_at']
