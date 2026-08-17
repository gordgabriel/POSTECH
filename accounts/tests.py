from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase

from accounts.models import UserModel
from accounts.permissions import (
    IsAdmin,
    IsAtendente,
    IsCliente,
    IsEstoquista,
    IsMecanico,
    IsOperador,
    has_any_role,
)

class APITestCaseBase(APITestCase):
    """
    Autentica um admin, que acumula todos os papéis.

    Os testes de fluxo verificam comportamento de domínio, não autorização;
    autenticar por papel em cada um deles só acrescentaria ruído. Quem cobre a
    matriz papel x operação é PermissoesPorPapelTests, em so/tests.py.
    Use autenticar_como() quando o papel importar para o teste.
    """

    def setUp(self):
        self.operador = self.criar_operador('admin_ops', UserModel.Tipo.ADMIN)
        self.autenticar(self.operador)

    def criar_operador(self, username, tipo):
        return UserModel.objects.create_user(
            username=username,
            email=f'{username}@test.com',
            password='senha12345',
            type=tipo,
        )

    def autenticar(self, usuario):
        self.client.force_authenticate(user=usuario)
        return usuario

    def autenticar_como(self, tipo):
        usuario = UserModel.objects.filter(type=tipo).first() or self.criar_operador(
            f'op_{tipo}', tipo,
        )
        return self.autenticar(usuario)

    def autenticar_por_jwt(self, username='admin_ops', senha='senha12345'):
        """Autenticação real pela rota de token, para o que precisa do JWT."""
        self.client.force_authenticate(user=None)
        resposta = self.client.post(
            reverse('token_obtain_pair'),
            {'username': username, 'password': senha},
            format='json',
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {resposta.data['access']}",
        )
        return resposta


class HealthCheckTests(APITestCase):
    def test_health_check_is_public(self):
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'ok')


class UserRegistrationTests(APITestCase):
    def test_register_user(self):
        response = self.client.post(
            '/api/users/',
            {
                'username': 'novo',
                'email': 'novo@test.com',
                'password': 'senha12345',
                'name': 'Novo Usuário',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(UserModel.objects.filter(username='novo').exists())

    def test_user_sem_type_nao_e_operador(self):
        user = UserModel.objects.create_user(
            username='cliente',
            email='cliente@test.com',
            password='senha12345',
        )
        self.assertFalse(user.is_operador)

    def test_user_com_type_e_operador(self):
        user = UserModel.objects.create_user(
            username='mecanico',
            email='mecanico@test.com',
            password='senha12345',
            type=UserModel.Tipo.MECANICO,
        )
        self.assertTrue(user.is_operador)


class ProfileTests(APITestCaseBase):
    def test_profile_retorna_usuario_logado(self):
        response = self.client.get('/api/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], self.operador.username)
        self.assertEqual(response.data['type'], self.operador.type)


class UserModelTests(APITestCase):
    def test_str_retorna_username(self):
        user = UserModel.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='senha12345',
        )
        self.assertEqual(str(user), 'testuser')

    def test_get_full_name(self):
        user = UserModel.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='senha12345',
            first_name='João',
            last_name='Silva',
        )
        self.assertEqual(user.get_full_name(), 'João Silva')

    def test_staff_e_operador_mesmo_sem_type(self):
        user = UserModel.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='senha12345',
            is_staff=True,
        )
        self.assertTrue(user.is_operador)
        self.assertTrue(user.is_admin)

    def test_type_admin_e_admin(self):
        user = UserModel.objects.create_user(
            username='admin_ops',
            email='admin_ops@test.com',
            password='senha12345',
            type=UserModel.Tipo.ADMIN,
        )
        self.assertTrue(user.is_admin)
        self.assertTrue(user.is_operador)
        self.assertFalse(user.is_cliente)

    def test_cliente_sem_type(self):
        user = UserModel.objects.create_user(
            username='cliente2',
            email='cliente2@test.com',
            password='senha12345',
        )
        self.assertTrue(user.is_cliente)
        self.assertFalse(user.is_operador)


class PermissionTests(APITestCase):
    factory = APIRequestFactory()

    def _check(self, permission_class, user, expected):
        request = self.factory.get('/')
        request.user = user
        self.assertEqual(permission_class().has_permission(request, None), expected)

    def test_anonimo_nega_todas_permissions(self):
        anon = AnonymousUser()
        for perm in (IsAdmin, IsAtendente, IsMecanico, IsEstoquista, IsOperador, IsCliente):
            self._check(perm, anon, False)

    def test_atendente(self):
        user = UserModel.objects.create_user(
            username='at',
            email='at@test.com',
            password='senha12345',
            type=UserModel.Tipo.ATENDENTE,
        )
        self._check(IsAtendente, user, True)
        self._check(IsOperador, user, True)
        self._check(IsMecanico, user, False)
        self._check(IsCliente, user, False)

    def test_mecanico(self):
        user = UserModel.objects.create_user(
            username='mec',
            email='mec@test.com',
            password='senha12345',
            type=UserModel.Tipo.MECANICO,
        )
        self._check(IsMecanico, user, True)
        self._check(IsAtendente, user, False)

    def test_estoquista(self):
        user = UserModel.objects.create_user(
            username='est',
            email='est@test.com',
            password='senha12345',
            type=UserModel.Tipo.ESTOQUISTA,
        )
        self._check(IsEstoquista, user, True)
        self._check(IsMecanico, user, False)

    def test_type_admin_passa_is_admin_e_faz_bypass(self):
        user = UserModel.objects.create_user(
            username='adm',
            email='adm@test.com',
            password='senha12345',
            type=UserModel.Tipo.ADMIN,
        )
        self._check(IsAdmin, user, True)
        self._check(IsAtendente, user, True)
        self._check(IsMecanico, user, True)
        self._check(IsEstoquista, user, True)

    def test_is_staff_passa_is_admin_e_faz_bypass(self):
        user = UserModel.objects.create_user(
            username='staff',
            email='staff@test.com',
            password='senha12345',
            is_staff=True,
        )
        self._check(IsAdmin, user, True)
        self._check(IsMecanico, user, True)

    def test_cliente_passa_is_cliente(self):
        user = UserModel.objects.create_user(
            username='cli',
            email='cli@test.com',
            password='senha12345',
        )
        self._check(IsCliente, user, True)
        self._check(IsOperador, user, False)

    def test_has_any_role_atendente_ou_mecanico(self):
        perm = has_any_role(IsAtendente, IsMecanico)()
        atendente = UserModel.objects.create_user(
            username='at2',
            email='at2@test.com',
            password='senha12345',
            type=UserModel.Tipo.ATENDENTE,
        )
        mecanico = UserModel.objects.create_user(
            username='mec2',
            email='mec2@test.com',
            password='senha12345',
            type=UserModel.Tipo.MECANICO,
        )
        estoquista = UserModel.objects.create_user(
            username='est2',
            email='est2@test.com',
            password='senha12345',
            type=UserModel.Tipo.ESTOQUISTA,
        )
        request = self.factory.get('/')
        request.user = atendente
        self.assertTrue(perm.has_permission(request, None))
        request.user = mecanico
        self.assertTrue(perm.has_permission(request, None))
        request.user = estoquista
        self.assertFalse(perm.has_permission(request, None))


class UserViewSetTests(APITestCaseBase):
    def setUp(self):
        super().setUp()
        self.outro = UserModel.objects.create_user(
            username='outro',
            email='outro@test.com',
            password='senha12345',
            type=UserModel.Tipo.MECANICO,
        )

    def test_operador_nao_lista_usuarios(self):
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_operador_ve_apenas_proprio_detalhe(self):
        response = self.client.get(f'/api/users/{self.outro.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        response = self.client.get(f'/api/users/{self.operador.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], self.operador.username)

    def test_admin_lista_todos_usuarios(self):
        admin = UserModel.objects.create_superuser(
            username='super',
            email='super@test.com',
            password='senha12345',
        )
        self.client.force_authenticate(user=admin)
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 2)

    def test_admin_remove_usuario(self):
        admin = UserModel.objects.create_superuser(
            username='super',
            email='super@test.com',
            password='senha12345',
        )
        self.client.force_authenticate(user=admin)
        response = self.client.delete(f'/api/users/{self.outro.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(UserModel.objects.filter(pk=self.outro.id).exists())
