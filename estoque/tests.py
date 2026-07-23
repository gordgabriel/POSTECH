from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import UserModel
from estoque.models import PecaEstoque


class PecaEstoqueAPITests(APITestCase):
    def setUp(self):
        self.user = UserModel.objects.create_user(
            username='teste',
            email='teste@example.com',
            password='senha123',
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse('peca-estoque-list')

    def test_crud_completo_da_peca(self):
        payload = {
            'nome': 'Parafuso M8',
            'quantidade': 15,
            'quantidade_reservada': 2,
            'descricao': 'Parafuso metálico para montagem',
        }

        create_response = self.client.post(self.url, payload, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data['nome'], payload['nome'])
        self.assertEqual(create_response.data['quantidade_reservada'], payload['quantidade_reservada'])

        peca = PecaEstoque.objects.get(pk=create_response.data['id'])
        detail_url = reverse('peca-estoque-detail', kwargs={'pk': peca.pk})

        list_response = self.client.get(self.url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(list_response.data), 1)

        update_payload = {
            'nome': 'Parafuso M8 inox',
            'quantidade': 20,
            'quantidade_reservada': 3,
            'descricao': 'Parafuso inox atualizado',
        }
        update_response = self.client.put(detail_url, update_payload, format='json')
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data['nome'], update_payload['nome'])
        self.assertEqual(update_response.data['quantidade'], update_payload['quantidade'])
        self.assertEqual(update_response.data['quantidade_reservada'], update_payload['quantidade_reservada'])

        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(PecaEstoque.objects.filter(pk=peca.pk).exists())

    def test_increment_quantidade_reservada_endpoint(self):
        payload = {
            'nome': 'Arruela',
            'quantidade': 2,
            'quantidade_reservada': 0,
            'descricao': 'Arruela metálica',
        }

        create_response = self.client.post(self.url, payload, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        peca_id = create_response.data['id']

        reservar_url = reverse('peca-estoque-reservar', kwargs={'pk': peca_id})

        resp1 = self.client.post(reservar_url)
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(resp1.data['quantidade_reservada'], 1)

        resp2 = self.client.post(reservar_url)
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data['quantidade_reservada'], 2)

        # terceira tentativa deve falhar (quantidade total = 2)
        resp3 = self.client.post(reservar_url)
        self.assertEqual(resp3.status_code, status.HTTP_400_BAD_REQUEST)
