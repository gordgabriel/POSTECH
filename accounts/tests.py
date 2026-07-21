from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import UserModel, VehiclesModel
from so.models import OSModel


class APITestCaseBase(APITestCase):
    def setUp(self):
        self.user = UserModel.objects.create_user(
            username='cliente',
            email='cliente@test.com',
            password='senha12345',
        )
        self.responsible = UserModel.objects.create_user(
            username='mecanico',
            email='mecanico@test.com',
            password='senha12345',
        )
        login_response = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'cliente', 'password': 'senha12345'},
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
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(UserModel.objects.filter(username='novo').exists())


class VehicleTests(APITestCaseBase):
    def test_create_and_list_vehicle(self):
        response = self.client.post(
            '/api/vehicles/',
            {
                'brand': 'Fiat',
                'model': 'Uno',
                'year': 2015,
                'plate': 'XYZ9A87',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(VehiclesModel.objects.count(), 1)
        self.assertEqual(response.data['user'], self.user.id)

        list_response = self.client.get('/api/vehicles/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)


class ServiceOrderTests(APITestCaseBase):
    def test_create_and_list_service_order(self):
        response = self.client.post(
            '/api/service-orders/',
            {
                'description': 'Revisao geral',
                'responsible': self.responsible.id,
                'status': 'Received',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(OSModel.objects.count(), 1)
        self.assertEqual(response.data['user'], self.user.id)

        list_response = self.client.get('/api/service-orders/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
