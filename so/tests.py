from decimal import Decimal
from datetime import timedelta

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import override_settings
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

        def comando(nome):
            response = self.client.post(f'/api/ordens-servico/{os_.id}/{nome}/')
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                msg=f'Falhou no comando {nome}: {response.data}',
            )

        response = self.client.post(
            f'/api/ordens-servico/{os_.id}/diagnosticar/',
            {'diagnostico': 'Correia desgastada'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        ItemServicoOS.objects.create(
            ordem_servico=os_,
            servico=self.servico,
            quantidade=1,
            preco_unitario=self.servico.preco,
        )
        orcamento = Orcamento.gerar_para_os(os_)
        self.client.post(f'/api/orcamentos/{orcamento.id}/enviar/')
        self.client.post(f'/api/orcamentos/{orcamento.id}/aprovar/')

        comando('finalizar')
        comando('entregar')

        os_.refresh_from_db()
        self.assertEqual(os_.status, StatusOS.ENTREGUE)
        self.assertIsNotNone(os_.data_diagnostico)
        self.assertIsNotNone(os_.data_inicio_execucao)
        self.assertIsNotNone(os_.data_finalizacao)
        self.assertIsNotNone(os_.data_entrega)

    def test_patch_de_status_nao_muda_a_etapa(self):
        os_ = self.criar_os()
        response = self.client.patch(
            f'/api/ordens-servico/{os_.id}/',
            {'status': StatusOS.ENTREGUE},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], StatusOS.RECEBIDA)

        os_.refresh_from_db()
        self.assertEqual(os_.status, StatusOS.RECEBIDA)
        self.assertIsNone(os_.data_entrega)

    def test_patch_nao_grava_diagnostico_sem_o_comando(self):
        os_ = self.criar_os()
        self.client.patch(
            f'/api/ordens-servico/{os_.id}/',
            {'diagnostico': 'Correia desgastada'},
            format='json',
        )
        os_.refresh_from_db()
        self.assertIsNone(os_.diagnostico)
        self.assertEqual(os_.status, StatusOS.RECEBIDA)

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

    def test_item_novo_entra_no_orcamento_ainda_aberto(self):
        """Antes do envio o orçamento continua sendo montado, não vira outro."""
        self.adicionar_itens()
        orcamento = Orcamento.em_aberto(self.os)
        self.assertEqual(orcamento.sequencia, 1)
        total_antes = orcamento.valor_total

        ItemServicoOS.objects.create(
            ordem_servico=self.os,
            servico=self.servico,
            quantidade=1,
            preco_unitario=None,
        )
        orcamento.refresh_from_db()
        self.assertEqual(self.os.orcamentos.count(), 1)
        self.assertEqual(orcamento.valor_total, total_antes + Decimal('150.00'))

    def test_orcamento_adicional_cobre_apenas_itens_novos(self):
        self.os.status = StatusOS.EM_DIAGNOSTICO
        self.os.save()
        self.adicionar_itens()
        inicial = Orcamento.em_aberto(self.os)
        inicial.enviar()

        # Reparo adicional: só depois do envio é que o item abre outro orçamento.
        ItemServicoOS.objects.create(
            ordem_servico=self.os,
            servico=self.servico,
            quantidade=1,
            preco_unitario=None,
        )
        adicional = Orcamento.em_aberto(self.os)
        self.assertEqual(adicional.sequencia, 2)
        self.assertEqual(adicional.valor_total, Decimal('150.00'))

    def test_aprovar_e_recusar_orcamento(self):
        self.os.status = StatusOS.EM_DIAGNOSTICO
        self.os.save()
        self.adicionar_itens()
        orcamento = Orcamento.gerar_para_os(self.os)
        self.client.post(f'/api/orcamentos/{orcamento.id}/enviar/')
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
        self.os.status = StatusOS.EM_DIAGNOSTICO
        self.os.save()
        self.adicionar_itens()
        orcamento = Orcamento.gerar_para_os(self.os)
        response = self.client.post(f'/api/orcamentos/{orcamento.id}/enviar/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['data_envio'])

    def test_enviar_com_os_em_recebida_retorna_400(self):
        self.adicionar_itens()
        orcamento = Orcamento.gerar_para_os(self.os)
        response = self.client.post(f'/api/orcamentos/{orcamento.id}/enviar/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        orcamento.refresh_from_db()
        self.os.refresh_from_db()
        self.assertIsNone(orcamento.data_envio)
        self.assertEqual(self.os.status, StatusOS.RECEBIDA)

    def test_responder_sem_envio_retorna_400_e_nao_marca_o_orcamento(self):
        self.os.status = StatusOS.EM_DIAGNOSTICO
        self.os.save()
        self.adicionar_itens()
        orcamento = Orcamento.gerar_para_os(self.os)

        response = self.client.post(f'/api/orcamentos/{orcamento.id}/aprovar/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        orcamento.refresh_from_db()
        self.os.refresh_from_db()
        self.assertEqual(orcamento.status, Orcamento.Status.PENDENTE)
        self.assertIsNone(orcamento.data_resposta)
        self.assertEqual(self.os.status, StatusOS.EM_DIAGNOSTICO)


class ComandoDiagnosticarTests(OSTestCaseBase):
    """Comando Realizar diagnóstico -> status Em diagnóstico."""

    def diagnosticar(self, os_, parecer='Correia desgastada'):
        return self.client.post(
            f'/api/ordens-servico/{os_.id}/diagnosticar/',
            {'diagnostico': parecer},
            format='json',
        )

    def test_diagnosticar_grava_parecer_e_avanca_status(self):
        os_ = self.criar_os()
        response = self.diagnosticar(os_)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], StatusOS.EM_DIAGNOSTICO)
        self.assertEqual(response.data['diagnostico'], 'Correia desgastada')
        self.assertIsNotNone(response.data['data_diagnostico'])

    def test_diagnosticar_sem_parecer_retorna_400(self):
        os_ = self.criar_os()
        response = self.client.post(
            f'/api/ordens-servico/{os_.id}/diagnosticar/',
            {'diagnostico': '   '},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('diagnostico', response.data)
        os_.refresh_from_db()
        self.assertEqual(os_.status, StatusOS.RECEBIDA)

    def test_revisar_parecer_com_os_ja_em_diagnostico(self):
        os_ = self.criar_os()
        self.diagnosticar(os_)
        response = self.diagnosticar(os_, 'Correia e tensor desgastados')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        os_.refresh_from_db()
        self.assertEqual(os_.diagnostico, 'Correia e tensor desgastados')
        self.assertEqual(os_.status, StatusOS.EM_DIAGNOSTICO)

    def test_diagnosticar_os_entregue_retorna_400_e_nao_grava(self):
        os_ = self.criar_os(status=StatusOS.ENTREGUE)
        response = self.diagnosticar(os_)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        os_.refresh_from_db()
        self.assertIsNone(os_.diagnostico)
        self.assertEqual(os_.status, StatusOS.ENTREGUE)


class TransicoesAutomaticasTests(OSTestCaseBase):

    def test_enviar_orcamento_avanca_para_aguardando_aprovacao(self):
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
        # Gerar não é evento pivotal: a OS só avança no envio.
        os_.refresh_from_db()
        self.assertEqual(os_.status, StatusOS.EM_DIAGNOSTICO)

        response = self.client.post(
            f'/api/orcamentos/{response.data["id"]}/enviar/',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        os_.refresh_from_db()
        self.assertEqual(os_.status, StatusOS.AGUARDANDO_APROVACAO)


@override_settings(EMAIL_OPERACAO='operacao@test.com')
class EstoqueIntegracaoTests(OSTestCaseBase):
    """A reserva acontece na aprovação do orçamento, não na inclusão do item."""

    def setUp(self):
        super().setUp()
        self.os = self.criar_os(status=StatusOS.EM_DIAGNOSTICO)

    def item(self, quantidade, os_=None):
        return ItemPecaOS.objects.create(
            ordem_servico=os_ or self.os,
            peca=self.peca,
            quantidade=quantidade,
            preco_unitario=self.peca.preco,
        )

    def aprovar(self, os_=None):
        orcamento = Orcamento.gerar_para_os(os_ or self.os)
        orcamento.enviar()
        orcamento.responder(aprovado=True)
        return orcamento

    def test_incluir_peca_nao_reserva_estoque(self):
        response = self.client.post(
            '/api/itens-peca/',
            {'ordem_servico': self.os.id, 'peca': self.peca.id, 'quantidade': 3},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade_reservada, 0)
        self.assertEqual(self.peca.quantidade_disponivel, 10)

    def test_aprovar_orcamento_reserva_as_pecas(self):
        self.item(3)
        self.aprovar()
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade_reservada, 3)
        self.assertEqual(self.peca.quantidade_disponivel, 7)

    def test_incluir_mais_do_que_existe_e_aceito_ate_a_aprovacao(self):
        response = self.client.post(
            '/api/itens-peca/',
            {'ordem_servico': self.os.id, 'peca': self.peca.id, 'quantidade': 99},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade_reservada, 0)

    def test_aprovar_sem_estoque_pausa_a_os_e_notifica(self):
        self.item(99)
        orcamento = Orcamento.gerar_para_os(self.os)
        orcamento.enviar()
        mail.outbox.clear()

        response = self.client.post(f'/api/orcamentos/{orcamento.id}/aprovar/')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('faltantes', response.data)
        self.assertEqual(response.data['faltantes'][0]['solicitado'], 99)
        self.assertEqual(response.data['faltantes'][0]['disponivel'], 10)

        orcamento.refresh_from_db()
        self.os.refresh_from_db()
        self.peca.refresh_from_db()
        # A OS fica pausada onde está e a resposta não é gravada: o cliente
        # aprova de novo quando a peça chegar.
        self.assertEqual(self.os.status, StatusOS.AGUARDANDO_APROVACAO)
        self.assertEqual(orcamento.status, Orcamento.Status.PENDENTE)
        self.assertEqual(self.peca.quantidade_reservada, 0)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('estoque insuficiente', mail.outbox[0].subject.lower())

    def test_reposicao_destrava_a_aprovacao(self):
        self.item(99)
        orcamento = Orcamento.gerar_para_os(self.os)
        orcamento.enviar()
        self.client.post(f'/api/orcamentos/{orcamento.id}/aprovar/')

        self.peca.quantidade = 120
        self.peca.save()
        response = self.client.post(f'/api/orcamentos/{orcamento.id}/aprovar/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.os.refresh_from_db()
        self.assertEqual(self.os.status, StatusOS.EM_EXECUCAO)

    def test_reserva_e_tudo_ou_nada(self):
        outra = Peca.objects.create(
            nome='Correia dentada',
            preco=Decimal('90.00'),
            quantidade=50,
        )
        self.item(2)
        ItemPecaOS.objects.create(
            ordem_servico=self.os,
            peca=outra,
            quantidade=999,
            preco_unitario=outra.preco,
        )
        orcamento = Orcamento.gerar_para_os(self.os)
        orcamento.enviar()

        response = self.client.post(f'/api/orcamentos/{orcamento.id}/aprovar/')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.peca.refresh_from_db()
        outra.refresh_from_db()
        self.assertEqual(self.peca.quantidade_reservada, 0)
        self.assertEqual(outra.quantidade_reservada, 0)

    def test_baixa_estoque_na_entrega(self):
        self.item(2)
        self.aprovar()
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade_reservada, 2)

        self.os.refresh_from_db()
        self.os.transitar_para(StatusOS.FINALIZADA)
        self.os.transitar_para(StatusOS.ENTREGUE)

        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade, 8)
        self.assertEqual(self.peca.quantidade_reservada, 0)

    def test_encerrar_os_libera_reserva(self):
        self.item(2)
        self.aprovar()
        self.os.refresh_from_db()
        self.assertEqual(self.peca_reservada(), 2)

        self.os.encerrar()

        self.os.refresh_from_db()
        self.peca.refresh_from_db()
        self.assertFalse(self.os.is_active)
        # Encerrar não é etapa: o status guarda até onde o atendimento chegou.
        self.assertEqual(self.os.status, StatusOS.EM_EXECUCAO)
        self.assertEqual(self.peca.quantidade_reservada, 0)
        self.assertEqual(self.peca.quantidade, 10)

    def peca_reservada(self):
        self.peca.refresh_from_db()
        return self.peca.quantidade_reservada

    def test_preco_unitario_vem_do_catalogo_quando_nulo(self):
        item = ItemPecaOS.objects.create(
            ordem_servico=self.os,
            peca=self.peca,
            quantidade=1,
        )
        self.assertEqual(item.preco_unitario, self.peca.preco)

    def test_mudar_quantidade_antes_da_aprovacao_nao_mexe_no_estoque(self):
        item = self.item(2)
        item.quantidade = 5
        item.save()
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade_reservada, 0)

    def test_aumentar_quantidade_depois_de_aprovado_reserva_mais(self):
        item = self.item(2)
        self.aprovar()
        item.refresh_from_db()
        item.quantidade = 5
        item.save()
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade_reservada, 5)

    def test_diminuir_quantidade_depois_de_aprovado_libera(self):
        item = self.item(5)
        self.aprovar()
        item.refresh_from_db()
        item.quantidade = 2
        item.save()
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade_reservada, 2)

    def test_excluir_item_aprovado_libera_reserva(self):
        item = self.item(3)
        self.aprovar()
        item.refresh_from_db()
        item.delete()
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade_reservada, 0)

    def test_excluir_item_nao_aprovado_nao_mexe_no_estoque(self):
        item = self.item(3)
        item.delete()
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade_reservada, 0)
        self.assertEqual(self.peca.quantidade, 10)

    def test_str_do_item(self):
        item = self.item(2)
        self.assertEqual(str(item), f'2x {self.peca.nome}')


@override_settings(EMAIL_OPERACAO='operacao@test.com')
class AlertaEstoqueMinimoTests(OSTestCaseBase):
    """Política: estoque abaixo do mínimo, então alertar reposição."""

    def setUp(self):
        super().setUp()
        self.peca.estoque_minimo = 8
        self.peca.save()
        self.os = self.criar_os(status=StatusOS.EM_DIAGNOSTICO)

    def aprovar_com(self, quantidade):
        ItemPecaOS.objects.create(
            ordem_servico=self.os,
            peca=self.peca,
            quantidade=quantidade,
            preco_unitario=self.peca.preco,
        )
        orcamento = Orcamento.gerar_para_os(self.os)
        orcamento.enviar()
        mail.outbox.clear()
        # O alerta sai em on_commit, que não roda sozinho dentro do TestCase.
        with self.captureOnCommitCallbacks(execute=True):
            orcamento.responder(aprovado=True)
        self.os.refresh_from_db()

    def test_reserva_que_fura_o_minimo_alerta(self):
        # 10 em estoque, mínimo 8: reservar 3 deixa 7 disponíveis.
        self.aprovar_com(3)
        alertas = [m for m in mail.outbox if 'mínimo' in m.subject.lower()]
        self.assertEqual(len(alertas), 1)
        self.assertIn(self.peca.nome, alertas[0].body)

    def test_reserva_que_nao_fura_o_minimo_nao_alerta(self):
        self.aprovar_com(2)
        alertas = [m for m in mail.outbox if 'mínimo' in m.subject.lower()]
        self.assertEqual(len(alertas), 0)

    def test_baixa_na_entrega_alerta(self):
        self.aprovar_com(3)
        self.os.transitar_para(StatusOS.FINALIZADA)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.os.transitar_para(StatusOS.ENTREGUE)

        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade, 7)
        alertas = [m for m in mail.outbox if 'mínimo' in m.subject.lower()]
        self.assertEqual(len(alertas), 1)

    def test_alerta_vai_para_a_oficina_e_nao_para_o_cliente(self):
        self.aprovar_com(3)
        alertas = [m for m in mail.outbox if 'mínimo' in m.subject.lower()]
        self.assertEqual(alertas[0].to, ['operacao@test.com'])
        self.assertNotIn(self.cliente.email, alertas[0].to)


class OrcamentoAutomaticoTests(OSTestCaseBase):
    """Política: itens incluídos, então gerar o orçamento automaticamente."""

    def setUp(self):
        super().setUp()
        self.os = self.criar_os(status=StatusOS.EM_DIAGNOSTICO)

    def incluir_servico(self, quantidade=1):
        return self.client.post(
            '/api/itens-servico/',
            {
                'ordem_servico': self.os.id,
                'servico': self.servico.id,
                'quantidade': quantidade,
            },
            format='json',
        )

    def test_incluir_item_gera_o_orcamento_sozinho(self):
        self.assertEqual(self.os.orcamentos.count(), 0)
        self.incluir_servico()
        self.assertEqual(self.os.orcamentos.count(), 1)
        orcamento = self.os.orcamentos.first()
        self.assertEqual(orcamento.sequencia, 1)
        self.assertEqual(orcamento.valor_total, self.servico.preco)
        self.assertEqual(orcamento.status, Orcamento.Status.PENDENTE)

    def test_gerar_nao_move_a_os(self):
        self.incluir_servico()
        self.os.refresh_from_db()
        self.assertEqual(self.os.status, StatusOS.EM_DIAGNOSTICO)

    def test_cada_item_novo_soma_no_mesmo_orcamento(self):
        self.incluir_servico()
        ItemPecaOS.objects.create(
            ordem_servico=self.os,
            peca=self.peca,
            quantidade=2,
            preco_unitario=self.peca.preco,
        )
        self.assertEqual(self.os.orcamentos.count(), 1)
        orcamento = self.os.orcamentos.first()
        self.assertEqual(
            orcamento.valor_total,
            self.servico.preco + 2 * self.peca.preco,
        )

    def test_mudar_quantidade_atualiza_o_total(self):
        self.incluir_servico()
        item = self.os.itens_servico.first()
        item.quantidade = 3
        item.save()
        orcamento = self.os.orcamentos.first()
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.valor_total, 3 * self.servico.preco)

    def test_depois_do_envio_item_novo_abre_o_adicional(self):
        self.incluir_servico()
        orcamento = Orcamento.em_aberto(self.os)
        self.client.post(f'/api/orcamentos/{orcamento.id}/enviar/')

        self.incluir_servico()
        self.assertEqual(self.os.orcamentos.count(), 2)
        adicional = Orcamento.em_aberto(self.os)
        self.assertEqual(adicional.sequencia, 2)
        self.assertEqual(adicional.valor_total, self.servico.preco)

    def test_post_em_orcamentos_continua_funcionando(self):
        """O endpoint manual segue válido e devolve o orçamento em aberto."""
        self.incluir_servico()
        response = self.client.post(
            '/api/orcamentos/',
            {'ordem_servico': self.os.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.os.orcamentos.count(), 1)
        self.assertEqual(response.data['sequencia'], 1)

    def test_os_sem_itens_nao_tem_orcamento(self):
        response = self.client.post(
            '/api/orcamentos/',
            {'ordem_servico': self.os.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class IdentificarClientePorDocumentoTests(OSTestCaseBase):
    """Comando Identificar cliente por CPF/CNPJ."""

    def setUp(self):
        super().setUp()
        self.outro = Cliente.objects.create(
            cpf_cnpj='11.444.777/0001-61',
            nome='Transportes Rápido LTDA',
            email='contato@transportes.com',
        )

    def buscar(self, documento):
        return self.client.get(f'/api/clientes/?cpf_cnpj={documento}')

    def test_encontra_com_pontuacao(self):
        response = self.buscar('529.982.247-25')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.cliente.id)

    def test_encontra_so_com_digitos(self):
        response = self.buscar('52998224725')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.cliente.id)

    def test_encontra_cnpj(self):
        response = self.buscar('11444777000161')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.outro.id)

    def test_documento_inexistente_devolve_lista_vazia(self):
        self.assertEqual(len(self.buscar('390.533.447-05').data), 0)

    def test_sem_filtro_lista_todos(self):
        response = self.client.get('/api/clientes/')
        self.assertEqual(len(response.data), Cliente.objects.count())

    def test_filtro_sem_digito_nao_vaza_a_base(self):
        self.assertEqual(len(self.buscar('abc').data), 0)


class PermissoesPorPapelTests(OSTestCaseBase):
    """Matriz papel x operação da seção 4 da Linguagem Ubíqua."""

    def setUp(self):
        super().setUp()
        self.atendente = self.criar_operador('ate', UserModel.Tipo.ATENDENTE)
        self.mecanico = self.criar_operador('mec', UserModel.Tipo.MECANICO)
        self.estoquista = self.criar_operador('est', UserModel.Tipo.ESTOQUISTA)
        self.usuario_cliente = UserModel.objects.create_user(
            username='cliente_joao',
            email='cliente.joao@test.com',
            password='senha12345',
        )
        self.cliente.usuario = self.usuario_cliente
        self.cliente.save()
        self.os = self.criar_os()

    def como(self, usuario, metodo, url, dados=None):
        self.autenticar(usuario)
        chamada = getattr(self.client, metodo)
        if dados is None:
            return chamada(url)
        return chamada(url, dados, format='json')

    def assertPermite(self, usuario, metodo, url, dados=None):
        resposta = self.como(usuario, metodo, url, dados)
        self.assertNotIn(
            resposta.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED),
            msg=f'{usuario.type or "cliente"} foi barrado em {metodo.upper()} {url}',
        )
        return resposta

    def assertBloqueia(self, usuario, metodo, url, dados=None):
        resposta = self.como(usuario, metodo, url, dados)
        self.assertIn(
            resposta.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            msg=(
                f'{usuario.type or "cliente"} NAO foi barrado em '
                f'{metodo.upper()} {url}: HTTP {resposta.status_code}'
            ),
        )
        return resposta

    # ------------------------------------------------------------ comandos da OS
    def test_abrir_os_e_do_atendente(self):
        dados = {
            'descricao': 'nova',
            'cliente': self.cliente.id,
            'veiculo': self.veiculo.id,
        }
        self.assertPermite(self.atendente, 'post', '/api/ordens-servico/', dados)
        for usuario in (self.mecanico, self.estoquista, self.usuario_cliente):
            self.assertBloqueia(usuario, 'post', '/api/ordens-servico/', dados)

    def test_diagnosticar_e_do_mecanico(self):
        url = f'/api/ordens-servico/{self.os.id}/diagnosticar/'
        dados = {'diagnostico': 'correia'}
        for usuario in (self.atendente, self.estoquista, self.usuario_cliente):
            self.assertBloqueia(usuario, 'post', url, dados)
        self.assertPermite(self.mecanico, 'post', url, dados)

    def test_finalizar_e_do_mecanico(self):
        url = f'/api/ordens-servico/{self.os.id}/finalizar/'
        for usuario in (self.atendente, self.estoquista, self.usuario_cliente):
            self.assertBloqueia(usuario, 'post', url)

    def test_entregar_e_cancelar_sao_do_atendente(self):
        for comando in ('entregar', 'cancelar'):
            url = f'/api/ordens-servico/{self.os.id}/{comando}/'
            for usuario in (self.mecanico, self.estoquista, self.usuario_cliente):
                self.assertBloqueia(usuario, 'post', url)

    def test_cliente_nao_finaliza_nem_entrega_a_propria_os(self):
        """Era a falha mais grave: o cliente dava baixa no estoque da oficina."""
        for comando in ('finalizar', 'entregar'):
            self.assertBloqueia(
                self.usuario_cliente,
                'post',
                f'/api/ordens-servico/{self.os.id}/{comando}/',
            )

    # ------------------------------------------------------------ itens e orçamento
    def test_incluir_servico_vale_para_mecanico_e_atendente(self):
        dados = {
            'ordem_servico': self.os.id,
            'servico': self.servico.id,
            'quantidade': 1,
        }
        self.assertPermite(self.mecanico, 'post', '/api/itens-servico/', dados)
        # O atendente inclui serviço porque é ele quem recebe o pedido do
        # cliente; serviço é item de catálogo e não reserva estoque.
        self.assertPermite(self.atendente, 'post', '/api/itens-servico/', dados)
        for usuario in (self.estoquista, self.usuario_cliente):
            self.assertBloqueia(usuario, 'post', '/api/itens-servico/', dados)

    def test_incluir_peca_e_so_do_mecanico(self):
        dados = {
            'ordem_servico': self.os.id,
            'peca': self.peca.id,
            'quantidade': 1,
        }
        self.assertPermite(self.mecanico, 'post', '/api/itens-peca/', dados)
        # Peça reserva estoque e exige juízo técnico: fica com o mecânico.
        for usuario in (self.atendente, self.estoquista, self.usuario_cliente):
            self.assertBloqueia(usuario, 'post', '/api/itens-peca/', dados)

    def test_gerar_e_do_mecanico_enviar_e_do_atendente(self):
        self.os.status = StatusOS.EM_DIAGNOSTICO
        self.os.save()
        ItemServicoOS.objects.create(
            ordem_servico=self.os,
            servico=self.servico,
            quantidade=1,
            preco_unitario=self.servico.preco,
        )
        dados = {'ordem_servico': self.os.id}
        self.assertBloqueia(self.atendente, 'post', '/api/orcamentos/', dados)
        resposta = self.assertPermite(self.mecanico, 'post', '/api/orcamentos/', dados)
        orcamento_id = resposta.data['id']

        url = f'/api/orcamentos/{orcamento_id}/enviar/'
        self.assertBloqueia(self.mecanico, 'post', url)
        self.assertPermite(self.atendente, 'post', url)

    def test_aprovar_e_do_cliente_ou_do_atendente(self):
        self.os.status = StatusOS.EM_DIAGNOSTICO
        self.os.save()
        ItemServicoOS.objects.create(
            ordem_servico=self.os,
            servico=self.servico,
            quantidade=1,
            preco_unitario=self.servico.preco,
        )
        orcamento = Orcamento.gerar_para_os(self.os)
        self.autenticar(self.atendente)
        self.client.post(f'/api/orcamentos/{orcamento.id}/enviar/')

        self.assertBloqueia(
            self.mecanico, 'post', f'/api/orcamentos/{orcamento.id}/aprovar/',
        )
        self.assertPermite(
            self.usuario_cliente, 'post', f'/api/orcamentos/{orcamento.id}/aprovar/',
        )

    # ------------------------------------------------------------ cadastros
    def test_cliente_nao_enxerga_cadastro_de_terceiros(self):
        """O vazamento de CPF/CNPJ: a listagem não pode devolver todo mundo."""
        outro = Cliente.objects.create(
            cpf_cnpj='11.444.777/0001-61',
            nome='Outra Pessoa',
            email='outra@test.com',
        )
        self.autenticar(self.usuario_cliente)
        resposta = self.client.get('/api/clientes/')
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        ids = [c['id'] for c in resposta.data]
        self.assertEqual(ids, [self.cliente.id])
        self.assertNotIn(outro.id, ids)

        self.assertBloqueia(self.usuario_cliente, 'get', f'/api/clientes/{outro.id}/')

    def test_operador_enxerga_todos_os_clientes(self):
        self.autenticar(self.mecanico)
        resposta = self.client.get('/api/clientes/')
        self.assertEqual(len(resposta.data), Cliente.objects.count())

    def test_escrita_de_cadastro_e_do_atendente(self):
        dados = {
            'cpf_cnpj': '390.533.447-05',
            'nome': 'Maria',
            'email': 'maria@test.com',
        }
        self.assertPermite(self.atendente, 'post', '/api/clientes/', dados)
        for usuario in (self.mecanico, self.estoquista, self.usuario_cliente):
            self.assertBloqueia(usuario, 'post', '/api/clientes/', dados)

    def test_catalogo_de_servico_so_o_admin_altera(self):
        dados = {'nome': 'Novo', 'preco': '10.00', 'tempo_execucao': 5}
        for usuario in (self.atendente, self.mecanico, self.usuario_cliente):
            self.assertBloqueia(usuario, 'post', '/api/servicos/', dados)
        self.assertPermite(self.operador, 'post', '/api/servicos/', dados)

    def test_cliente_nao_altera_preco_do_catalogo(self):
        self.assertBloqueia(
            self.usuario_cliente,
            'patch',
            f'/api/servicos/{self.servico.id}/',
            {'preco': '0.01'},
        )

    # ------------------------------------------------------------ estoque
    def test_estoque_e_do_estoquista_e_invisivel_ao_cliente(self):
        dados = {'nome': 'Peça nova', 'preco': '10.00', 'quantidade': 5}
        self.assertPermite(self.estoquista, 'post', '/api/pecas/', dados)
        for usuario in (self.atendente, self.mecanico, self.usuario_cliente):
            self.assertBloqueia(usuario, 'post', '/api/pecas/', dados)

        self.assertBloqueia(self.usuario_cliente, 'get', '/api/pecas/')
        self.assertBloqueia(
            self.usuario_cliente,
            'patch',
            f'/api/pecas/{self.peca.id}/',
            {'quantidade': 9999},
        )
        self.assertPermite(self.mecanico, 'get', '/api/pecas/')

    def test_relatorio_e_so_para_operador(self):
        url = '/api/relatorios/tempo-medio-execucao/'
        self.assertBloqueia(self.usuario_cliente, 'get', url)
        for usuario in (self.atendente, self.mecanico, self.estoquista):
            self.assertPermite(usuario, 'get', url)


class RemocaoProtegidaTests(OSTestCaseBase):
    """PROTECT preserva o histórico; a API deve dizer 409, não estourar 500."""

    def setUp(self):
        super().setUp()
        self.os = self.criar_os()
        ItemServicoOS.objects.create(
            ordem_servico=self.os,
            servico=self.servico,
            quantidade=1,
            preco_unitario=self.servico.preco,
        )
        ItemPecaOS.objects.create(
            ordem_servico=self.os,
            peca=self.peca,
            quantidade=1,
            preco_unitario=self.peca.preco,
        )

    def test_remover_cliente_com_os_retorna_409(self):
        response = self.client.delete(f'/api/clientes/{self.cliente.id}/')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('detail', response.data)
        self.assertTrue(Cliente.objects.filter(pk=self.cliente.pk).exists())

    def test_remover_veiculo_com_os_retorna_409(self):
        response = self.client.delete(f'/api/veiculos/{self.veiculo.id}/')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(Veiculo.objects.filter(pk=self.veiculo.pk).exists())

    def test_remover_servico_com_item_de_os_retorna_409(self):
        response = self.client.delete(f'/api/servicos/{self.servico.id}/')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(Servico.objects.filter(pk=self.servico.pk).exists())

    def test_remover_peca_com_item_de_os_retorna_409(self):
        response = self.client.delete(f'/api/pecas/{self.peca.id}/')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(Peca.objects.filter(pk=self.peca.pk).exists())

    def test_remover_cadastro_sem_vinculo_continua_funcionando(self):
        livre = Servico.objects.create(
            nome='Serviço sem uso',
            preco=Decimal('10.00'),
            tempo_execucao=10,
        )
        response = self.client.delete(f'/api/servicos/{livre.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Servico.objects.filter(pk=livre.pk).exists())


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


class RespostaOrcamentoTests(OSTestCaseBase):
    """Consequências da recusa e do reparo adicional no fluxo da OS."""

    def item_peca(self, os_, quantidade):
        return ItemPecaOS.objects.create(
            ordem_servico=os_,
            peca=self.peca,
            quantidade=quantidade,
            preco_unitario=self.peca.preco,
        )

    def orcamento_enviado(self, os_):
        """Devolve instância limpa: o envio muda a OS no banco."""
        orcamento = Orcamento.gerar_para_os(os_)
        response = self.client.post(f'/api/orcamentos/{orcamento.id}/enviar/')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        os_.refresh_from_db()
        return Orcamento.objects.get(pk=orcamento.pk)

    def aprovar(self, orcamento):
        response = self.client.post(f'/api/orcamentos/{orcamento.id}/aprovar/')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response

    def test_recusa_do_orcamento_inicial_devolve_para_diagnostico(self):
        """O cliente achou caro: o mecânico revê os itens e propõe de novo."""
        os_ = self.criar_os(status=StatusOS.EM_DIAGNOSTICO)
        self.item_peca(os_, 3)
        orcamento = self.orcamento_enviado(os_)

        response = self.client.post(f'/api/orcamentos/{orcamento.id}/recusar/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], Orcamento.Status.RECUSADO)

        os_.refresh_from_db()
        self.peca.refresh_from_db()
        self.assertEqual(os_.status, StatusOS.EM_DIAGNOSTICO)
        self.assertTrue(os_.is_active)
        # Nada estava reservado: orçamento recusado nunca foi aprovado.
        self.assertEqual(self.peca.quantidade_reservada, 0)
        self.assertEqual(self.peca.quantidade, 10)

    def test_recusa_de_adicional_mantem_os_em_execucao(self):
        os_ = self.criar_os(status=StatusOS.EM_DIAGNOSTICO)
        self.item_peca(os_, 3)
        self.aprovar(self.orcamento_enviado(os_))
        os_.refresh_from_db()
        self.assertEqual(os_.status, StatusOS.EM_EXECUCAO)

        # Reparo adicional durante a execução.
        self.item_peca(os_, 4)
        adicional = self.orcamento_enviado(os_)
        self.assertEqual(adicional.sequencia, 2)
        os_.refresh_from_db()
        self.assertEqual(os_.status, StatusOS.AGUARDANDO_APROVACAO)

        self.client.post(f'/api/orcamentos/{adicional.id}/recusar/')

        os_.refresh_from_db()
        self.peca.refresh_from_db()
        self.assertEqual(os_.status, StatusOS.EM_EXECUCAO)
        # O adicional nunca reservou, porque não chegou a ser aprovado.
        # As 3 peças do orçamento inicial seguem reservadas.
        self.assertEqual(self.peca.quantidade_reservada, 3)

    def test_adicional_devolve_os_para_aguardando_aprovacao(self):
        os_ = self.criar_os(status=StatusOS.EM_EXECUCAO)
        ItemServicoOS.objects.create(
            ordem_servico=os_,
            servico=self.servico,
            quantidade=1,
            preco_unitario=self.servico.preco,
        )
        self.orcamento_enviado(os_)
        os_.refresh_from_db()
        self.assertEqual(os_.status, StatusOS.AGUARDANDO_APROVACAO)

    def test_recusa_de_adicional_tira_os_itens_da_os(self):
        """O que o cliente recusou não fica pendurado na OS."""
        os_ = self.criar_os(status=StatusOS.EM_DIAGNOSTICO)
        self.item_peca(os_, 3)
        self.aprovar(self.orcamento_enviado(os_))
        os_.refresh_from_db()
        self.assertEqual(os_.itens_peca.count(), 1)

        # Reparo adicional com dois itens.
        self.item_peca(os_, 4)
        ItemServicoOS.objects.create(
            ordem_servico=os_,
            servico=self.servico,
            quantidade=1,
            preco_unitario=self.servico.preco,
        )
        adicional = self.orcamento_enviado(os_)
        self.assertEqual(os_.itens_peca.count(), 2)
        self.assertEqual(os_.itens_servico.count(), 1)

        self.client.post(f'/api/orcamentos/{adicional.id}/recusar/')

        os_.refresh_from_db()
        self.peca.refresh_from_db()
        # Sobrou só o item do orçamento aprovado.
        self.assertEqual(os_.itens_peca.count(), 1)
        self.assertEqual(os_.itens_servico.count(), 0)
        self.assertEqual(os_.itens_peca.first().quantidade, 3)
        # A reserva do que foi aprovado não foi tocada.
        self.assertEqual(self.peca.quantidade_reservada, 3)
        # O orçamento recusado fica como histórico do que foi proposto.
        adicional.refresh_from_db()
        self.assertEqual(adicional.status, Orcamento.Status.RECUSADO)
        self.assertGreater(adicional.valor_total, 0)

    def test_recusa_do_inicial_tira_os_itens_e_volta_para_diagnostico(self):
        os_ = self.criar_os(status=StatusOS.EM_DIAGNOSTICO)
        self.item_peca(os_, 3)
        orcamento = self.orcamento_enviado(os_)

        self.client.post(f'/api/orcamentos/{orcamento.id}/recusar/')

        os_.refresh_from_db()
        self.peca.refresh_from_db()
        self.assertEqual(os_.status, StatusOS.EM_DIAGNOSTICO)
        self.assertEqual(os_.itens_peca.count(), 0)
        self.assertEqual(self.peca.quantidade_reservada, 0)
        self.assertEqual(self.peca.quantidade, 10)

    def test_item_reproposto_depois_da_recusa_entra_em_orcamento_novo(self):
        """Depois da recusa o mecânico remonta a proposta do zero."""
        os_ = self.criar_os(status=StatusOS.EM_DIAGNOSTICO)
        self.item_peca(os_, 5)
        orcamento = self.orcamento_enviado(os_)
        self.client.post(f'/api/orcamentos/{orcamento.id}/recusar/')

        # Reoferta mais barata.
        self.item_peca(os_, 1)
        novo = Orcamento.em_aberto(os_)
        self.assertEqual(novo.sequencia, 2)
        self.assertEqual(novo.itens_peca.count(), 1)
        self.assertEqual(novo.itens_peca.first().quantidade, 1)
        self.assertLess(novo.valor_total, orcamento.valor_total)

    def test_enviar_orcamento_ja_respondido_retorna_400(self):
        os_ = self.criar_os(status=StatusOS.EM_DIAGNOSTICO)
        self.item_peca(os_, 1)
        orcamento = self.orcamento_enviado(os_)
        self.aprovar(orcamento)

        response = self.client.post(f'/api/orcamentos/{orcamento.id}/enviar/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)


class ComandosOrdemServicoTests(OSTestCaseBase):
    """Comandos Finalizar OS, Registrar entrega e Cancelar OS."""

    def incluir_peca(self, ordem_servico, quantidade=2):
        return ItemPecaOS.objects.create(
            ordem_servico=ordem_servico,
            peca=self.peca,
            quantidade=quantidade,
            preco_unitario=self.peca.preco,
        )

    def incluir_peca_aprovada(self, ordem_servico, quantidade=2):
        """Inclui e aprova, que é o que de fato reserva a peça no estoque."""
        item = self.incluir_peca(ordem_servico, quantidade)
        orcamento = Orcamento.gerar_para_os(ordem_servico)
        orcamento.enviar()
        orcamento.responder(aprovado=True)
        ordem_servico.refresh_from_db()
        return item

    def test_finalizar_os_em_execucao(self):
        os_ = self.criar_os(status=StatusOS.EM_EXECUCAO)
        response = self.client.post(f'/api/ordens-servico/{os_.id}/finalizar/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], StatusOS.FINALIZADA)
        self.assertIsNotNone(response.data['data_finalizacao'])

    def test_finalizar_os_recebida_retorna_400(self):
        os_ = self.criar_os()
        response = self.client.post(f'/api/ordens-servico/{os_.id}/finalizar/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)
        os_.refresh_from_db()
        self.assertEqual(os_.status, StatusOS.RECEBIDA)

    def test_entregar_os_finalizada_baixa_estoque(self):
        os_ = self.criar_os(status=StatusOS.EM_DIAGNOSTICO)
        self.incluir_peca_aprovada(os_)
        os_.transitar_para(StatusOS.FINALIZADA)

        response = self.client.post(f'/api/ordens-servico/{os_.id}/entregar/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], StatusOS.ENTREGUE)
        self.assertIsNotNone(response.data['data_entrega'])

        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade, 8)
        self.assertEqual(self.peca.quantidade_reservada, 0)

    def test_entregar_os_recebida_retorna_400(self):
        os_ = self.criar_os()
        response = self.client.post(f'/api/ordens-servico/{os_.id}/entregar/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)
        os_.refresh_from_db()
        self.assertEqual(os_.status, StatusOS.RECEBIDA)

    def test_encerrar_os_libera_reserva_e_mantem_o_status(self):
        os_ = self.criar_os(status=StatusOS.EM_DIAGNOSTICO)
        self.incluir_peca(os_)
        orcamento = Orcamento.gerar_para_os(os_)
        orcamento.enviar()
        orcamento.responder(aprovado=True)
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade_reservada, 2)

        response = self.client.post(f'/api/ordens-servico/{os_.id}/encerrar/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_active'])
        # O status não muda: ele registra até onde o atendimento chegou.
        self.assertEqual(response.data['status'], StatusOS.EM_EXECUCAO)

        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade_reservada, 0)
        self.assertEqual(self.peca.quantidade, 10)

    def test_encerrar_os_recebida(self):
        os_ = self.criar_os()
        response = self.client.post(f'/api/ordens-servico/{os_.id}/encerrar/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_active'])
        self.assertEqual(response.data['status'], StatusOS.RECEBIDA)

    def test_encerrar_duas_vezes_retorna_400(self):
        os_ = self.criar_os()
        self.client.post(f'/api/ordens-servico/{os_.id}/encerrar/')
        response = self.client.post(f'/api/ordens-servico/{os_.id}/encerrar/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_os_encerrada_sai_da_listagem(self):
        ativa = self.criar_os()
        encerrada = self.criar_os()
        self.client.post(f'/api/ordens-servico/{encerrada.id}/encerrar/')

        ids = [o['id'] for o in self.client.get('/api/ordens-servico/').data]
        self.assertIn(ativa.id, ids)
        self.assertNotIn(encerrada.id, ids)

        ids = [
            o['id']
            for o in self.client.get('/api/ordens-servico/?is_active=false').data
        ]
        self.assertIn(encerrada.id, ids)
        self.assertNotIn(ativa.id, ids)

        ids = [
            o['id']
            for o in self.client.get('/api/ordens-servico/?is_active=todas').data
        ]
        self.assertIn(ativa.id, ids)
        self.assertIn(encerrada.id, ids)

    def test_encerrada_continua_acessivel_pelo_id(self):
        """Sai da listagem, mas o histórico não some."""
        os_ = self.criar_os()
        self.client.post(f'/api/ordens-servico/{os_.id}/encerrar/')
        response = self.client.get(f'/api/ordens-servico/{os_.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_active'])

    def test_encerrar_os_entregue_retorna_400(self):
        """OS entregue está concluída: o serviço foi prestado."""
        os_ = self.criar_os(status=StatusOS.FINALIZADA)
        os_.transitar_para(StatusOS.ENTREGUE)
        response = self.client.post(f'/api/ordens-servico/{os_.id}/encerrar/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)


class HistoricoClienteVeiculoTests(OSTestCaseBase):
    """Modelo de leitura Histórico do cliente e do veículo, da seção 8 da Ubíqua."""

    def setUp(self):
        super().setUp()
        self.outro_cliente = Cliente.objects.create(
            cpf_cnpj='11144477735',
            nome='Maria Souza',
            email='maria@test.com',
        )
        self.outro_veiculo = Veiculo.objects.create(
            placa='XYZ9K88',
            marca='VW',
            modelo='Gol',
            ano=2020,
            cliente=self.outro_cliente,
        )
        self.os_joao = self.criar_os()
        self.os_maria = self.criar_os(
            cliente=self.outro_cliente,
            veiculo=self.outro_veiculo,
        )

    def ids(self, url):
        return [o['id'] for o in self.client.get(url).data]

    def test_filtra_por_cliente(self):
        ids = self.ids(f'/api/ordens-servico/?cliente={self.cliente.id}')
        self.assertEqual(ids, [self.os_joao.id])

    def test_filtra_por_veiculo(self):
        ids = self.ids(f'/api/ordens-servico/?veiculo={self.outro_veiculo.id}')
        self.assertEqual(ids, [self.os_maria.id])

    def test_filtra_por_uuid(self):
        """O serializer expõe id e uuid; os dois servem para consultar."""
        ids = self.ids(f'/api/ordens-servico/?cliente={self.cliente.uuid}')
        self.assertEqual(ids, [self.os_joao.id])

    def test_cliente_e_veiculo_juntos(self):
        ids = self.ids(
            f'/api/ordens-servico/?cliente={self.cliente.id}'
            f'&veiculo={self.outro_veiculo.id}'
        )
        self.assertEqual(ids, [])

    def test_valor_invalido_devolve_lista_vazia(self):
        """Consulta que não acha nada não é erro."""
        response = self.client.get('/api/ordens-servico/?cliente=nao-existe')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(list(response.data), [])

    def test_sem_filtro_traz_todas(self):
        ids = self.ids('/api/ordens-servico/')
        self.assertCountEqual(ids, [self.os_joao.id, self.os_maria.id])

    def test_historico_respeita_o_encerramento(self):
        """O filtro soma ao is_active, não o substitui."""
        self.client.post(f'/api/ordens-servico/{self.os_joao.id}/encerrar/')
        url = f'/api/ordens-servico/?cliente={self.cliente.id}'
        self.assertEqual(self.ids(url), [])
        self.assertEqual(self.ids(url + '&is_active=false'), [self.os_joao.id])
