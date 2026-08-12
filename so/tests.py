from decimal import Decimal
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import status

from accounts.models import UserModel
from accounts.tests import APITestCaseBase
from cadastros.models import Cliente, Servico, Veiculo
from estoque.models import Peca
from so.models import ItemPecaOS, ItemServicoOS, Orcamento, OrdemServico, StatusOS


class OSTestCaseBase(APITestCaseBase):
    def setUp(self):
        super().setUp()
        self.cliente = Cliente.objects.create(
            cpf_cnpj='529.982.247-25',
            nome='João da Silva',
            email='joao@test.com',
        )
        self.veiculo = Veiculo.objects.create(
            placa='ABC1D23',
            marca='Fiat',
            modelo='Uno',
            ano=2015,
            cliente=self.cliente,
        )
        self.servico = Servico.objects.create(
            nome='Troca de óleo',
            preco=Decimal('150.00'),
            tempo_execucao=60,
        )
        self.peca = Peca.objects.create(
            nome='Filtro de óleo',
            preco=Decimal('40.00'),
            quantidade=10,
        )

    def criar_os(self, **kwargs):
        dados = {
            'descricao': 'Motor fazendo barulho',
            'cliente': self.cliente,
            'veiculo': self.veiculo,
        }
        dados.update(kwargs)
        return OrdemServico.objects.create(**dados)


class OrdemServicoAPITests(OSTestCaseBase):
    def test_criar_os(self):
        response = self.client.post(
            '/api/ordens-servico/',
            {
                'descricao': 'Motor fazendo barulho',
                'cliente': self.cliente.id,
                'veiculo': self.veiculo.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], StatusOS.RECEBIDA)
        self.assertIsNotNone(response.data['data_abertura'])

    def test_veiculo_de_outro_cliente_e_rejeitado(self):
        outro_cliente = Cliente.objects.create(
            cpf_cnpj='11.444.777/0001-61',
            nome='Outra Pessoa',
            email='outra@test.com',
        )
        response = self.client.post(
            '/api/ordens-servico/',
            {
                'descricao': 'Barulho',
                'cliente': outro_cliente.id,
                'veiculo': self.veiculo.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('veiculo', response.data)

    def test_cliente_logado_ve_apenas_suas_os(self):
        self.criar_os()
        usuario_cliente = UserModel.objects.create_user(
            username='joao',
            email='joao.login@test.com',
            password='senha12345',
        )
        outro_cliente = Cliente.objects.create(
            cpf_cnpj='11.444.777/0001-61',
            nome='Outra Pessoa',
            email='outra@test.com',
            usuario=usuario_cliente,
        )
        outro_veiculo = Veiculo.objects.create(
            placa='XYZ9A87',
            marca='VW',
            modelo='Gol',
            ano=2018,
            cliente=outro_cliente,
        )
        self.criar_os(cliente=outro_cliente, veiculo=outro_veiculo)

        self.client.force_authenticate(user=usuario_cliente)
        response = self.client.get('/api/ordens-servico/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['cliente'], outro_cliente.id)


class TransicaoStatusTests(OSTestCaseBase):
    def test_fluxo_completo_ate_entrega(self):
        os_ = self.criar_os()
        for novo_status in [
            StatusOS.EM_DIAGNOSTICO,
            StatusOS.AGUARDANDO_APROVACAO,
            StatusOS.EM_EXECUCAO,
            StatusOS.FINALIZADA,
            StatusOS.ENTREGUE,
        ]:
            response = self.client.patch(
                f'/api/ordens-servico/{os_.id}/',
                {'status': novo_status},
                format='json',
            )
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                msg=f'Falhou ao transitar para {novo_status}: {response.data}',
            )

        os_.refresh_from_db()
        self.assertEqual(os_.status, StatusOS.ENTREGUE)
        self.assertIsNotNone(os_.data_diagnostico)
        self.assertIsNotNone(os_.data_inicio_execucao)
        self.assertIsNotNone(os_.data_finalizacao)
        self.assertIsNotNone(os_.data_entrega)

    def test_pular_etapa_e_rejeitado(self):
        os_ = self.criar_os()
        response = self.client.patch(
            f'/api/ordens-servico/{os_.id}/',
            {'status': StatusOS.ENTREGUE},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('status', response.data)

    def test_reparo_adicional_volta_para_aguardando_aprovacao(self):
        os_ = self.criar_os(status=StatusOS.EM_EXECUCAO)
        response = self.client.patch(
            f'/api/ordens-servico/{os_.id}/',
            {'status': StatusOS.AGUARDANDO_APROVACAO},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_transicao_invalida_direto_no_model(self):
        os_ = self.criar_os()
        os_.status = StatusOS.FINALIZADA
        with self.assertRaises(ValidationError):
            os_.save()

    def test_data_inicio_execucao_nao_e_sobrescrita(self):
        os_ = self.criar_os(status=StatusOS.EM_EXECUCAO)
        # Simula reparo adicional: volta a aguardar aprovação e retoma.
        os_.status = StatusOS.AGUARDANDO_APROVACAO
        os_.save()
        os_.status = StatusOS.EM_EXECUCAO
        os_.save()
        os_.refresh_from_db()
        primeira_data = os_.data_inicio_execucao
        self.assertIsNotNone(primeira_data)

        os_.status = StatusOS.AGUARDANDO_APROVACAO
        os_.save()
        os_.status = StatusOS.EM_EXECUCAO
        os_.save()
        os_.refresh_from_db()
        self.assertEqual(os_.data_inicio_execucao, primeira_data)


class ItensETestesDeOrcamento(OSTestCaseBase):
    def setUp(self):
        super().setUp()
        self.os = self.criar_os()

    def adicionar_itens(self):
        self.client.post(
            '/api/itens-servico/',
            {
                'ordem_servico': self.os.id,
                'servico': self.servico.id,
                'quantidade': 1,
            },
            format='json',
        )
        self.client.post(
            '/api/itens-peca/',
            {
                'ordem_servico': self.os.id,
                'peca': self.peca.id,
                'quantidade': 2,
            },
            format='json',
        )

    def test_preco_unitario_e_congelado_do_catalogo(self):
        response = self.client.post(
            '/api/itens-servico/',
            {
                'ordem_servico': self.os.id,
                'servico': self.servico.id,
                'quantidade': 1,
                'preco_unitario': '1.00',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['preco_unitario'], '150.00')

        # Reajuste no catálogo não altera o item já incluído.
        self.servico.preco = Decimal('999.00')
        self.servico.save()
        item = ItemServicoOS.objects.get(pk=response.data['id'])
        self.assertEqual(item.preco_unitario, Decimal('150.00'))

    def test_gerar_orcamento_soma_itens(self):
        self.adicionar_itens()
        response = self.client.post(
            '/api/orcamentos/',
            {'ordem_servico': self.os.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # 1x 150.00 (serviço) + 2x 40.00 (peça) = 230.00
        self.assertEqual(response.data['valor_total'], '230.00')
        self.assertEqual(response.data['sequencia'], 1)

        item_servico = ItemServicoOS.objects.get(ordem_servico=self.os)
        item_peca = ItemPecaOS.objects.get(ordem_servico=self.os)
        self.assertEqual(item_servico.orcamento_id, response.data['id'])
        self.assertEqual(item_peca.orcamento_id, response.data['id'])

    def test_orcamento_sem_itens_pendentes_e_rejeitado(self):
        response = self.client.post(
            '/api/orcamentos/',
            {'ordem_servico': self.os.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_orcamento_adicional_cobre_apenas_itens_novos(self):
        self.adicionar_itens()
        Orcamento.gerar_para_os(self.os)

        # Reparo adicional: novo item incluído durante a execução.
        ItemServicoOS.objects.create(
            ordem_servico=self.os,
            servico=self.servico,
            quantidade=1,
            preco_unitario=None,
        )
        adicional = Orcamento.gerar_para_os(self.os)
        self.assertEqual(adicional.sequencia, 2)
        self.assertEqual(adicional.valor_total, Decimal('150.00'))

    def test_aprovar_e_recusar_orcamento(self):
        self.os.status = StatusOS.EM_DIAGNOSTICO
        self.os.save()
        self.adicionar_itens()
        orcamento = Orcamento.gerar_para_os(self.os)
        self.os.refresh_from_db()
        self.assertEqual(self.os.status, StatusOS.AGUARDANDO_APROVACAO)

        response = self.client.post(f'/api/orcamentos/{orcamento.id}/aprovar/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], Orcamento.Status.APROVADO)
        self.assertIsNotNone(response.data['data_resposta'])

        self.os.refresh_from_db()
        self.assertEqual(self.os.status, StatusOS.EM_EXECUCAO)

        # Orçamento já respondido não aceita nova resposta.
        response = self.client.post(f'/api/orcamentos/{orcamento.id}/recusar/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_enviar_orcamento_registra_data_envio(self):
        self.adicionar_itens()
        orcamento = Orcamento.gerar_para_os(self.os)
        response = self.client.post(f'/api/orcamentos/{orcamento.id}/enviar/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['data_envio'])


class TransicoesAutomaticasTests(OSTestCaseBase):
    def test_diagnostico_avanca_status_automaticamente(self):
        os_ = self.criar_os()
        response = self.client.patch(
            f'/api/ordens-servico/{os_.id}/',
            {'diagnostico': 'Correia desgastada'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], StatusOS.EM_DIAGNOSTICO)
        self.assertIsNotNone(response.data['data_diagnostico'])

    def test_gerar_orcamento_avanca_para_aguardando_aprovacao(self):
        os_ = self.criar_os(status=StatusOS.EM_DIAGNOSTICO)
        ItemServicoOS.objects.create(
            ordem_servico=os_,
            servico=self.servico,
            quantidade=1,
            preco_unitario=self.servico.preco,
        )
        response = self.client.post(
            '/api/orcamentos/',
            {'ordem_servico': os_.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        os_.refresh_from_db()
        self.assertEqual(os_.status, StatusOS.AGUARDANDO_APROVACAO)


class EstoqueIntegracaoTests(OSTestCaseBase):
    def setUp(self):
        super().setUp()
        self.os = self.criar_os()

    def test_reserva_estoque_ao_incluir_peca(self):
        response = self.client.post(
            '/api/itens-peca/',
            {
                'ordem_servico': self.os.id,
                'peca': self.peca.id,
                'quantidade': 3,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade_reservada, 3)
        self.assertEqual(self.peca.quantidade_disponivel, 7)

    def test_estoque_insuficiente_e_rejeitado(self):
        response = self.client.post(
            '/api/itens-peca/',
            {
                'ordem_servico': self.os.id,
                'peca': self.peca.id,
                'quantidade': 99,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('quantidade', response.data)

    def test_baixa_estoque_na_entrega(self):
        ItemPecaOS.objects.create(
            ordem_servico=self.os,
            peca=self.peca,
            quantidade=2,
            preco_unitario=self.peca.preco,
        )
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade_reservada, 2)

        for novo_status in [
            StatusOS.EM_DIAGNOSTICO,
            StatusOS.AGUARDANDO_APROVACAO,
            StatusOS.EM_EXECUCAO,
            StatusOS.FINALIZADA,
            StatusOS.ENTREGUE,
        ]:
            self.os.transitar_para(novo_status)

        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade, 8)
        self.assertEqual(self.peca.quantidade_reservada, 0)

    def test_libera_reserva_ao_cancelar_os(self):
        ItemPecaOS.objects.create(
            ordem_servico=self.os,
            peca=self.peca,
            quantidade=2,
            preco_unitario=self.peca.preco,
        )
        self.os.status = StatusOS.CANCELADA
        self.os.save()

        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade_reservada, 0)
        self.assertEqual(self.peca.quantidade, 10)

    def test_preco_unitario_vem_do_catalogo_quando_nulo(self):
        item = ItemPecaOS.objects.create(
            ordem_servico=self.os,
            peca=self.peca,
            quantidade=1,
        )
        self.assertEqual(item.preco_unitario, self.peca.preco)

    def test_aumentar_quantidade_reserva_mais_estoque(self):
        item = ItemPecaOS.objects.create(
            ordem_servico=self.os,
            peca=self.peca,
            quantidade=2,
            preco_unitario=self.peca.preco,
        )
        item.quantidade = 5
        item.save()
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade_reservada, 5)

    def test_diminuir_quantidade_libera_estoque(self):
        item = ItemPecaOS.objects.create(
            ordem_servico=self.os,
            peca=self.peca,
            quantidade=5,
            preco_unitario=self.peca.preco,
        )
        item.quantidade = 2
        item.save()
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade_reservada, 2)

    def test_excluir_item_libera_reserva(self):
        item = ItemPecaOS.objects.create(
            ordem_servico=self.os,
            peca=self.peca,
            quantidade=3,
            preco_unitario=self.peca.preco,
        )
        item.delete()
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade_reservada, 0)

    def test_str_do_item(self):
        item = ItemPecaOS.objects.create(
            ordem_servico=self.os,
            peca=self.peca,
            quantidade=2,
            preco_unitario=self.peca.preco,
        )
        self.assertEqual(str(item), f'2x {self.peca.nome}')


class RelatorioTempoMedioTests(OSTestCaseBase):
    def test_tempo_medio_execucao(self):
        os1 = self.criar_os(status=StatusOS.FINALIZADA)
        os1.data_inicio_execucao = timezone.now()
        os1.data_finalizacao = os1.data_inicio_execucao + timedelta(hours=2)
        os1.save()

        os2 = self.criar_os(status=StatusOS.FINALIZADA)
        os2.data_inicio_execucao = timezone.now()
        os2.data_finalizacao = os2.data_inicio_execucao + timedelta(hours=4)
        os2.save()

        response = self.client.get('/api/relatorios/tempo-medio-execucao/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_os'], 2)
        self.assertEqual(response.data['tempo_medio_horas'], 3.0)
        self.assertEqual(response.data['tempo_medio_minutos'], 180.0)

    def test_tempo_medio_sem_dados(self):
        response = self.client.get('/api/relatorios/tempo-medio-execucao/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_os'], 0)
        self.assertIsNone(response.data['tempo_medio_horas'])

    def test_tempo_medio_com_filtro_de_periodo(self):
        os1 = self.criar_os(status=StatusOS.FINALIZADA)
        os1.data_inicio_execucao = timezone.now() - timedelta(days=5)
        os1.data_finalizacao = os1.data_inicio_execucao + timedelta(hours=2)
        os1.save()

        os2 = self.criar_os(status=StatusOS.FINALIZADA)
        os2.data_inicio_execucao = timezone.now() - timedelta(days=40)
        os2.data_finalizacao = os2.data_inicio_execucao + timedelta(hours=8)
        os2.save()

        de = (timezone.now() - timedelta(days=15)).strftime('%Y-%m-%dT00:00:00')
        ate = timezone.now().strftime('%Y-%m-%dT23:59:59')
        response = self.client.get(
            f'/api/relatorios/tempo-medio-execucao/?de={de}&ate={ate}',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_os'], 1)
        self.assertEqual(response.data['tempo_medio_horas'], 2.0)
