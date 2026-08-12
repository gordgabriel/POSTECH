from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings

from cadastros.models import Cliente, Veiculo
from notifications.services.email_service import send_notification_email
from notifications.services.os_notifications import notificar_status_os
from so.models import OrdemServico, StatusOS


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='oficina@test.com',
)
class SendNotificationEmailTests(TestCase):
    def test_envia_email_com_template_correto(self):
        send_notification_email(
            to='cliente@test.com',
            template_key='os_em_diagnostico',
            context={
                'cliente_nome': 'João',
                'os_uuid': 'abc-123',
                'veiculo_placa': 'ABC1D23',
                'status_display': 'Em diagnóstico',
                'descricao': 'Barulho no motor',
                'diagnostico': '',
                'data_abertura': None,
                'status_anterior': 'Recebida',
            },
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['cliente@test.com'])
        self.assertIn('diagnóstico', mail.outbox[0].subject.lower())
        self.assertIn('João', mail.outbox[0].body)
        self.assertEqual(len(mail.outbox[0].alternatives), 1)

    def test_destinatario_vazio_nao_envia(self):
        result = send_notification_email(
            to='',
            template_key='os_em_diagnostico',
            context={'cliente_nome': 'João'},
        )
        self.assertEqual(result, 0)
        self.assertEqual(len(mail.outbox), 0)

    @patch('notifications.services.email_service.EmailMultiAlternatives.send')
    def test_falha_smtp_retorna_zero(self, mock_send):
        mock_send.side_effect = ConnectionError('SMTP indisponível')
        result = send_notification_email(
            to='cliente@test.com',
            template_key='os_em_diagnostico',
            context={
                'cliente_nome': 'João',
                'os_uuid': 'abc',
                'veiculo_placa': 'ABC1D23',
                'status_display': 'Em diagnóstico',
                'descricao': 'Teste',
                'diagnostico': '',
                'data_abertura': None,
                'status_anterior': 'Recebida',
            },
        )
        self.assertEqual(result, 0)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='oficina@test.com',
)
class NotificarStatusOSTests(TestCase):
    def setUp(self):
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
        self.os = OrdemServico.objects.create(
            descricao='Motor fazendo barulho',
            cliente=self.cliente,
            veiculo=self.veiculo,
        )
        mail.outbox.clear()

    def test_notifica_template_por_status(self):
        self.os.status = StatusOS.EM_DIAGNOSTICO
        self.os.save()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('diagnóstico', mail.outbox[0].subject.lower())

    def test_status_recebida_nao_notifica(self):
        result = notificar_status_os(self.os, None)
        self.assertEqual(result, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_transicao_dispara_email(self):
        mail.outbox.clear()
        self.os.transitar_para(StatusOS.EM_DIAGNOSTICO)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['joao@test.com'])

    def test_criacao_os_nao_envia_email(self):
        self.assertEqual(len(mail.outbox), 0)

    @patch('notifications.services.email_service.EmailMultiAlternatives.send')
    def test_falha_email_nao_impede_save(self, mock_send):
        mock_send.side_effect = ConnectionError('SMTP indisponível')
        self.os.transitar_para(StatusOS.EM_DIAGNOSTICO)
        self.os.refresh_from_db()
        self.assertEqual(self.os.status, StatusOS.EM_DIAGNOSTICO)
