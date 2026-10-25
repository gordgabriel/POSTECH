"""APIs da OS pedidas na Fase 2: status, listagem, webhook e abertura."""
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework import status

from accounts.models import UserModel
from cadastros.models import Cliente, Veiculo
from estoque.models import Peca
from so.models import ItemPecaOS, ItemServicoOS, Orcamento, OrdemServico, StatusOS
from so.tests import OSTestCaseBase


class ConsultaStatusTests(OSTestCaseBase):
    def url(self, chave):
        return f'/api/ordens-servico/{chave}/status/'

    def test_consulta_pelo_id(self):
        os_ = self.criar_os()
        response = self.client.get(self.url(os_.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data),
            {'id', 'uuid', 'status', 'status_display', 'atualizada_em'},
        )
        self.assertEqual(response.data['status'], StatusOS.RECEBIDA)
        self.assertEqual(response.data['status_display'], 'Recebida')

    def test_consulta_pela_uuid(self):
        os_ = self.criar_os(status=StatusOS.EM_DIAGNOSTICO)
        response = self.client.get(self.url(os_.uuid))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], os_.id)
        self.assertEqual(response.data['status'], StatusOS.EM_DIAGNOSTICO)

    def test_acompanha_a_transicao(self):
        os_ = self.criar_os()
        self.client.post(
            f'/api/ordens-servico/{os_.id}/diagnosticar/',
            {'diagnostico': 'Correia gasta'},
            format='json',
        )
        response = self.client.get(self.url(os_.uuid))
        self.assertEqual(response.data['status'], StatusOS.EM_DIAGNOSTICO)
        self.assertEqual(response.data['status_display'], 'Em diagnóstico')

    def test_os_encerrada_continua_consultavel(self):
        os_ = self.criar_os()
        self.client.post(f'/api/ordens-servico/{os_.id}/encerrar/')
        response = self.client.get(self.url(os_.uuid))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], StatusOS.RECEBIDA)

    def test_inexistente_ou_invalido_retorna_404(self):
        self.assertEqual(
            self.client.get(self.url(uuid.uuid4())).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(self.url(999999)).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(self.url('nao-e-uuid')).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_cliente_consulta_so_a_propria_os(self):
        usuario = UserModel.objects.create_user(
            username='maria', email='maria.login@test.com', password='senha12345',
        )
        maria = Cliente.objects.create(
            cpf_cnpj='11.444.777/0001-61',
            nome='Maria',
            email='maria@test.com',
            usuario=usuario,
        )
        veiculo_maria = Veiculo.objects.create(
            placa='XYZ9A87', marca='VW', modelo='Gol', ano=2018, cliente=maria,
        )
        da_maria = self.criar_os(cliente=maria, veiculo=veiculo_maria)
        do_joao = self.criar_os()

        self.client.force_authenticate(user=usuario)
        self.assertEqual(
            self.client.get(self.url(da_maria.uuid)).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.get(self.url(do_joao.uuid)).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_sem_token_retorna_401(self):
        os_ = self.criar_os()
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url(os_.uuid))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ListagemOSTests(OSTestCaseBase):
    URL = '/api/ordens-servico/'

    def criar_os_aberta_em(self, status_os, dias_atras):
        os_ = self.criar_os(status=status_os)
        OrdemServico.objects.filter(pk=os_.pk).update(
            data_abertura=timezone.now() - timedelta(days=dias_atras),
        )
        return os_

    def ids(self, url=URL):
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return [o['id'] for o in response.data]

    def test_ordena_por_status_e_mais_antigas_primeiro(self):
        recebida_nova = self.criar_os_aberta_em(StatusOS.RECEBIDA, 1)
        execucao_nova = self.criar_os_aberta_em(StatusOS.EM_EXECUCAO, 2)
        diagnostico = self.criar_os_aberta_em(StatusOS.EM_DIAGNOSTICO, 3)
        recebida_antiga = self.criar_os_aberta_em(StatusOS.RECEBIDA, 9)
        aguardando = self.criar_os_aberta_em(StatusOS.AGUARDANDO_APROVACAO, 4)
        execucao_antiga = self.criar_os_aberta_em(StatusOS.EM_EXECUCAO, 8)

        self.assertEqual(
            self.ids(),
            [
                execucao_antiga.id,
                execucao_nova.id,
                aguardando.id,
                diagnostico.id,
                recebida_antiga.id,
                recebida_nova.id,
            ],
        )

    def test_finalizada_e_entregue_ficam_fora_da_listagem(self):
        em_andamento = self.criar_os_aberta_em(StatusOS.RECEBIDA, 1)
        self.criar_os_aberta_em(StatusOS.FINALIZADA, 5)
        self.criar_os_aberta_em(StatusOS.ENTREGUE, 6)

        self.assertEqual(self.ids(), [em_andamento.id])
        self.assertEqual(self.ids(self.URL + '?is_active=true'), [em_andamento.id])

    def test_exclusao_e_logica(self):
        finalizada = self.criar_os_aberta_em(StatusOS.FINALIZADA, 1)
        self.assertNotIn(finalizada.id, self.ids())
        self.assertTrue(OrdemServico.objects.filter(pk=finalizada.pk).exists())
        response = self.client.get(f'{self.URL}{finalizada.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_historico_completo_traz_concluidas_no_fim(self):
        entregue = self.criar_os_aberta_em(StatusOS.ENTREGUE, 9)
        recebida = self.criar_os_aberta_em(StatusOS.RECEBIDA, 1)
        execucao = self.criar_os_aberta_em(StatusOS.EM_EXECUCAO, 2)
        finalizada = self.criar_os_aberta_em(StatusOS.FINALIZADA, 8)

        self.assertEqual(
            self.ids(self.URL + '?is_active=todas'),
            [execucao.id, recebida.id, entregue.id, finalizada.id],
        )

    def test_encerradas_seguem_a_mesma_ordem(self):
        recebida = self.criar_os_aberta_em(StatusOS.RECEBIDA, 1)
        execucao = self.criar_os_aberta_em(StatusOS.EM_EXECUCAO, 2)
        finalizada = self.criar_os_aberta_em(StatusOS.FINALIZADA, 3)
        OrdemServico.objects.filter(
            pk__in=[recebida.pk, execucao.pk, finalizada.pk],
        ).update(is_active=False)

        self.assertEqual(self.ids(), [])
        self.assertEqual(
            self.ids(self.URL + '?is_active=false'),
            [execucao.id, recebida.id, finalizada.id],
        )

    def test_filtro_por_cliente_respeita_a_exclusao(self):
        recebida = self.criar_os_aberta_em(StatusOS.RECEBIDA, 1)
        self.criar_os_aberta_em(StatusOS.FINALIZADA, 2)
        self.assertEqual(
            self.ids(f'{self.URL}?cliente={self.cliente.uuid}'),
            [recebida.id],
        )

    def test_ordenacao_nao_acrescenta_consultas(self):
        for dias in range(5):
            self.criar_os_aberta_em(StatusOS.RECEBIDA, dias)
        with self.assertNumQueries(4):
            self.client.get(self.URL)


@override_settings(WEBHOOK_TOKEN='segredo-do-webhook')
class WebhookOrcamentoTests(OSTestCaseBase):
    URL = '/api/webhooks/orcamento/'

    def setUp(self):
        super().setUp()
        self.os = self.criar_os(status=StatusOS.EM_DIAGNOSTICO)
        ItemPecaOS.objects.create(
            ordem_servico=self.os, peca=self.peca, quantidade=3,
            preco_unitario=self.peca.preco,
        )
        self.orcamento = Orcamento.objects.get(ordem_servico=self.os)
        self.orcamento.enviar()
        self.client.force_authenticate(user=None)

    def notificar(self, aprovado, token='segredo-do-webhook', orcamento=None):
        headers = {'HTTP_X_WEBHOOK_TOKEN': token} if token is not None else {}
        return self.client.post(
            self.URL,
            {'orcamento': str(orcamento or self.orcamento.uuid), 'aprovado': aprovado},
            format='json',
            **headers,
        )

    def test_aprovacao_reserva_e_inicia_a_execucao(self):
        response = self.notificar(True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], Orcamento.Status.APROVADO)
        self.os.refresh_from_db()
        self.peca.refresh_from_db()
        self.assertEqual(self.os.status, StatusOS.EM_EXECUCAO)
        self.assertEqual(self.peca.quantidade_reservada, 3)

    def test_recusa_volta_para_diagnostico(self):
        response = self.notificar(False)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], Orcamento.Status.RECUSADO)
        self.os.refresh_from_db()
        self.assertEqual(self.os.status, StatusOS.EM_DIAGNOSTICO)

    def test_reenvio_da_mesma_decisao_nao_repete_efeitos(self):
        self.notificar(True)
        mail.outbox.clear()
        response = self.notificar(True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], Orcamento.Status.APROVADO)
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade_reservada, 3)
        self.assertEqual(len(mail.outbox), 0)

    def test_decisao_contraria_retorna_409(self):
        self.notificar(True)
        response = self.notificar(False)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('já foi aprovado', response.data['detail'][0])
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, Orcamento.Status.APROVADO)

    def test_estoque_insuficiente_retorna_409_com_faltantes(self):
        Peca.objects.filter(pk=self.peca.pk).update(quantidade=1)
        response = self.notificar(True)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(
            response.data['faltantes'],
            [{'peca': self.peca.nome, 'solicitado': 3, 'disponivel': 1}],
        )
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, Orcamento.Status.PENDENTE)

    def test_orcamento_nao_enviado_retorna_400(self):
        outra = self.criar_os(status=StatusOS.EM_DIAGNOSTICO)
        ItemServicoOS.objects.create(
            ordem_servico=outra, servico=self.servico, quantidade=1,
            preco_unitario=self.servico.preco,
        )
        pendente = Orcamento.objects.get(ordem_servico=outra)
        response = self.notificar(True, orcamento=pendente.uuid)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_orcamento_inexistente_retorna_404(self):
        response = self.notificar(True, orcamento=uuid.uuid4())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_corpo_invalido_retorna_400(self):
        response = self.client.post(
            self.URL, {'orcamento': 'x'}, format='json',
            HTTP_X_WEBHOOK_TOKEN='segredo-do-webhook',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(set(response.data), {'orcamento', 'aprovado'})

    def test_token_errado_ou_ausente_retorna_403(self):
        self.assertEqual(self.notificar(True, token='outro').status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.notificar(True, token=None).status_code, status.HTTP_403_FORBIDDEN)
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, Orcamento.Status.PENDENTE)

    def test_jwt_de_usuario_nao_substitui_o_token(self):
        self.client.force_authenticate(user=self.operador)
        self.assertEqual(self.notificar(True, token=None).status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(WEBHOOK_TOKEN='')
    def test_sem_token_configurado_o_webhook_fica_fechado(self):
        self.assertEqual(self.notificar(True, token='').status_code, status.HTTP_403_FORBIDDEN)


class AberturaOSTests(OSTestCaseBase):
    URL = '/api/ordens-servico/abrir/'
    CPF_NOVO = '390.533.447-05'

    def setUp(self):
        super().setUp()
        self.autenticar_como(UserModel.Tipo.ATENDENTE)

    def corpo(self, **extra):
        dados = {
            'cliente': {'cpf_cnpj': self.CPF_NOVO, 'nome': 'Ana Lima', 'email': 'ana@test.com'},
            'veiculo': {'placa': 'BRA2E19', 'marca': 'Honda', 'modelo': 'Fit', 'ano': 2019},
            'descricao': 'Revisão dos 40 mil',
            'servicos': [{'servico': self.servico.id, 'quantidade': 1}],
            'pecas': [{'peca': self.peca.id, 'quantidade': 2}],
        }
        dados.update(extra)
        return dados

    def abrir(self, dados):
        return self.client.post(self.URL, dados, format='json')

    def test_cadastra_tudo_e_devolve_a_uuid(self):
        response = self.abrir(self.corpo())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        os_ = OrdemServico.objects.get(uuid=response.data['uuid'])
        self.assertEqual(os_.status, StatusOS.RECEBIDA)
        self.assertEqual(os_.cliente.cpf_cnpj, self.CPF_NOVO)
        self.assertEqual(os_.veiculo.placa, 'BRA2E19')
        self.assertEqual(os_.veiculo.cliente, os_.cliente)

        self.assertEqual(response.data['itens_servico'][0]['preco_unitario'], '150.00')
        self.assertEqual(response.data['itens_peca'][0]['quantidade'], 2)
        # 150 + 2 x 40
        self.assertEqual(len(response.data['orcamentos']), 1)
        self.assertEqual(response.data['orcamentos'][0]['valor_total'], '230.00')

    def test_peca_na_abertura_nao_reserva_estoque(self):
        self.abrir(self.corpo())
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade_reservada, 0)

    def test_reaproveita_cliente_e_veiculo_pelo_documento_e_pela_placa(self):
        response = self.abrir({
            'cliente': {'cpf_cnpj': '52998224725'},
            'veiculo': {'placa': 'abc-1d23'},
            'descricao': 'Retorno',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['cliente'], self.cliente.id)
        self.assertEqual(response.data['veiculo'], self.veiculo.id)
        self.assertEqual(Cliente.objects.count(), 1)
        self.assertEqual(Veiculo.objects.count(), 1)
        self.assertEqual(response.data['orcamentos'], [])

    def test_cliente_existente_com_veiculo_novo(self):
        response = self.abrir(self.corpo(cliente={'cpf_cnpj': self.cliente.cpf_cnpj}))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Veiculo.objects.get(placa='BRA2E19').cliente, self.cliente)

    def test_veiculo_de_outro_cliente_desfaz_tudo(self):
        response = self.abrir(self.corpo(veiculo={'placa': self.veiculo.placa}))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('veiculo', response.data)
        self.assertFalse(Cliente.objects.filter(cpf_cnpj=self.CPF_NOVO).exists())
        self.assertEqual(OrdemServico.objects.count(), 0)

    def test_falha_em_item_desfaz_cliente_veiculo_e_os(self):
        with patch(
            'so.repositorios.ItemPecaOS.objects.create',
            side_effect=RuntimeError('falha simulada'),
        ):
            with self.assertRaises(RuntimeError):
                self.abrir(self.corpo())
        self.assertFalse(Cliente.objects.filter(cpf_cnpj=self.CPF_NOVO).exists())
        self.assertFalse(Veiculo.objects.filter(placa='BRA2E19').exists())
        self.assertEqual(OrdemServico.objects.count(), 0)

    def test_cadastro_novo_incompleto_retorna_400_no_campo(self):
        response = self.abrir(self.corpo(cliente={'cpf_cnpj': self.CPF_NOVO}))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('nome, email', response.data['cliente'][0])

        response = self.abrir(self.corpo(veiculo={'placa': 'BRA2E19', 'marca': 'Honda'}))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('modelo, ano', response.data['veiculo'][0])
        self.assertEqual(OrdemServico.objects.count(), 0)

    def test_documento_e_placa_invalidos(self):
        response = self.abrir(self.corpo(
            cliente={'cpf_cnpj': '111.111.111-11', 'nome': 'X', 'email': 'x@test.com'},
            veiculo={'placa': 'XX-0000'},
        ))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cpf_cnpj', response.data['cliente'])
        self.assertIn('placa', response.data['veiculo'])

    def test_servico_inativo_ou_item_inexistente(self):
        self.servico.ativo = False
        self.servico.save()
        response = self.abrir(self.corpo(pecas=[{'peca': 999999, 'quantidade': 1}]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('servicos', response.data)
        self.assertIn('pecas', response.data)

    def test_quantidade_precisa_ser_positiva(self):
        response = self.abrir(self.corpo(pecas=[{'peca': self.peca.id, 'quantidade': 0}]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('pecas', response.data)

    def test_sem_itens_abre_so_a_os(self):
        response = self.abrir(self.corpo(servicos=[], pecas=[]))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['orcamentos'], [])

    def test_so_o_atendente_abre(self):
        self.autenticar_como(UserModel.Tipo.MECANICO)
        self.assertEqual(self.abrir(self.corpo()).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.abrir(self.corpo()).status_code, status.HTTP_401_UNAUTHORIZED)
