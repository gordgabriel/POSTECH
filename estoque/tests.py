from decimal import Decimal

from django.utils import timezone
from rest_framework import status

from accounts.tests import APITestCaseBase
from estoque.models import Peca


class EstoqueAlertasTests(APITestCaseBase):
    def test_alertas_lista_pecas_abaixo_do_minimo(self):
        Peca.objects.create(
            nome='Filtro crítico',
            preco=Decimal('40.00'),
            quantidade=2,
            quantidade_reservada=0,
            estoque_minimo=5,
        )
        Peca.objects.create(
            nome='Óleo ok',
            preco=Decimal('30.00'),
            quantidade=20,
            estoque_minimo=5,
        )
        response = self.client.get('/api/pecas/alertas/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['nome'], 'Filtro crítico')
        self.assertTrue(response.data[0]['abaixo_do_minimo'])
