from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import UserModel


class APITestCaseBase(APITestCase):
    """Autentica um operador (atendente) para os testes de API."""

    def setUp(self):
        self.operador = UserModel.objects.create_user(
            username='atendente',
            email='atendente@test.com',
            password='senha12345',
            type=UserModel.Tipo.ATENDENTE,
        )
        login_response = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'atendente', 'password': 'senha12345'},
            format='json',
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}",
        )


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
        self.assertEqual(response.data['username'], 'atendente')
        self.assertEqual(response.data['type'], 'atendente')
