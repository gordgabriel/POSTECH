from rest_framework import serializers

from accounts.models import UserModel


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserModel
        fields = [
            'id',
            'uuid',
            'username',
            'name',
            'email',
            'type',
            'first_name',
            'last_name',
            'phone_number',
            'is_active',
            'is_staff',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'uuid', 'type', 'is_staff', 'created_at', 'updated_at']


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    type = serializers.ChoiceField(
        choices=UserModel.Tipo.choices,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = UserModel
        fields = [
            'id',
            'uuid',
            'username',
            'name',
            'email',
            'password',
            'type',
            'first_name',
            'last_name',
            'phone_number',
        ]
        read_only_fields = ['id', 'uuid']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = UserModel(**validated_data)
        user.set_password(password)
        user.save()
        return user
