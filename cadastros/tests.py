from rest_framework import status

from accounts.tests import APITestCaseBase
from cadastros.models import Cliente, Veiculo

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
