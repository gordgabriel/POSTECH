from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from rest_framework import status

from accounts.tests import APITestCaseBase
from cadastros.models import Cliente, Servico, Veiculo
from cadastros.validators import validar_cpf_cnpj, validar_placa

CPF_VALIDO = '529.982.247-25'
CNPJ_VALIDO = '11.444.777/0001-61'


class ClienteTests(APITestCaseBase):
    def test_criar_cliente_com_cpf_valido(self):
        response = self.client.post(
            '/api/clientes/',
            {
                'cpf_cnpj': CPF_VALIDO,
                'nome': 'João da Silva',
                'email': 'joao@test.com',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Cliente.objects.count(), 1)

    def test_criar_cliente_com_cnpj_valido(self):
        response = self.client.post(
            '/api/clientes/',
            {
                'cpf_cnpj': CNPJ_VALIDO,
                'nome': 'Oficina Parceira LTDA',
                'email': 'contato@parceira.com',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_cpf_invalido_e_rejeitado(self):
        response = self.client.post(
            '/api/clientes/',
            {
                'cpf_cnpj': '111.111.111-11',
                'nome': 'Fraude',
                'email': 'x@test.com',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cpf_cnpj', response.data)

    def test_cpf_cnpj_e_unico(self):
        Cliente.objects.create(
            cpf_cnpj=CPF_VALIDO, nome='João', email='joao@test.com',
        )
        response = self.client.post(
            '/api/clientes/',
            {'cpf_cnpj': CPF_VALIDO, 'nome': 'Outro', 'email': 'outro@test.com'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class VeiculoTests(APITestCaseBase):
    def setUp(self):
        super().setUp()
        self.cliente = Cliente.objects.create(
            cpf_cnpj=CPF_VALIDO, nome='João', email='joao@test.com',
        )

    def test_criar_veiculo(self):
        response = self.client.post(
            '/api/veiculos/',
            {
                'placa': 'abc1d23',
                'marca': 'Fiat',
                'modelo': 'Uno',
                'ano': 2015,
                'cliente': self.cliente.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['placa'], 'ABC1D23')

    def test_placa_invalida_e_rejeitada(self):
        response = self.client.post(
            '/api/veiculos/',
            {
                'placa': '1234567',
                'marca': 'Fiat',
                'modelo': 'Uno',
                'ano': 2015,
                'cliente': self.cliente.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('placa', response.data)

    def test_placa_e_unica(self):
        Veiculo.objects.create(
            placa='ABC1D23',
            marca='Fiat',
            modelo='Uno',
            ano=2015,
            cliente=self.cliente,
        )
        response = self.client.post(
            '/api/veiculos/',
            {
                'placa': 'ABC1D23',
                'marca': 'VW',
                'modelo': 'Gol',
                'ano': 2018,
                'cliente': self.cliente.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ServicoTests(APITestCaseBase):
    def test_criar_servico(self):
        response = self.client.post(
            '/api/servicos/',
            {
                'nome': 'Troca de óleo',
                'descricao': 'Troca de óleo e filtro',
                'preco': '150.00',
                'tempo_execucao': 60,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['ativo'])


class ValidatorsTests(TestCase):
    def test_cpf_com_digitos_invalidos(self):
        with self.assertRaises(ValidationError):
            validar_cpf_cnpj('123.456.789-00')

    def test_cnpj_com_digitos_invalidos(self):
        with self.assertRaises(ValidationError):
            validar_cpf_cnpj('12.345.678/0001-00')

    def test_documento_com_tamanho_invalido(self):
        with self.assertRaises(ValidationError):
            validar_cpf_cnpj('12345')

    def test_placa_invalida(self):
        with self.assertRaises(ValidationError):
            validar_placa('INVALIDA')


class SeedDemoCommandTests(TestCase):
    def test_seed_demo_popula_banco(self):
        out = StringIO()
        call_command('seed_demo', stdout=out)
        self.assertGreater(Cliente.objects.count(), 0)
        self.assertGreater(Veiculo.objects.count(), 0)
        self.assertGreater(Servico.objects.count(), 0)
        self.assertIn('Seed concluído', out.getvalue())
