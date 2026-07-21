from rest_framework import serializers

from accounts.models import UserModel


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserModel
        fields = [
            'id',
            'uuid',
            'username',
            'email',
            'first_name',
            'last_name',
            'phone_number',
            'birth_date',
            'gender',
            'address',
            'is_active',
            'is_staff',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'uuid', 'is_staff', 'created_at', 'updated_at']


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = UserModel
        fields = [
            'id',
            'uuid',
            'username',
            'email',
            'password',
            'first_name',
            'last_name',
            'phone_number',
            'birth_date',
            'gender',
            'address',
        ]
        read_only_fields = ['id', 'uuid']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = UserModel(**validated_data)
        user.set_password(password)
        user.save()
        return user
