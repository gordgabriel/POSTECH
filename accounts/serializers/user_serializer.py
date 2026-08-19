from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

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

    def validate_type(self, valor):
        """O papel define a alçada do usuário, então só o admin o atribui.

        O cadastro fica aberto para que o cliente crie o próprio login e
        acompanhe suas ordens de serviço — mas quem se cadastra sozinho nasce
        sem papel, isto é, cliente. Operador é criado por admin autenticado ou
        pelo comando seed_users.
        """
        if not valor:
            return valor

        usuario = self.context['request'].user
        if not (usuario.is_authenticated and usuario.is_admin):
            raise PermissionDenied(
                'Definir o papel do usuário é operação de admin. '
                'Cadastro sem autenticação cria apenas login de cliente.',
            )
        return valor

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = UserModel(**validated_data)
        user.set_password(password)
        user.save()
        return user
