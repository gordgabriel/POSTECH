from rest_framework import serializers

from so.models import OSModel


class OSSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    responsible_username = serializers.CharField(
        source='responsible.username',
        read_only=True,
    )

    class Meta:
        model = OSModel
        fields = [
            'id',
            'uuid',
            'description',
            'is_active',
            'is_approved',
            'user',
            'user_username',
            'responsible',
            'responsible_username',
            'responsible_notes',
            'status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'uuid', 'user', 'created_at', 'updated_at']
