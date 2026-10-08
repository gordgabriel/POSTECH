"""
Fachadas de compatibilidade: a API antiga dos models e do EstoqueService
continua respondendo igual, agora repassando ao núcleo `oficina/`.
"""
from decimal import Decimal

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import override_settings

from estoque.services import EstoqueInsuficiente, EstoqueService
from so.models import ItemPecaOS, ItemServicoOS, Orcamento, OrdemServico, StatusOS
from so.tests import OSTestCaseBase


@override_settings(EMAIL_OPERACAO='operacao@test.com')
class EstoqueServiceTests(OSTestCaseBase):
    def aprovado(self, quantidade=2):
        os_ = self.criar_os(status=StatusOS.EM_DIAGNOSTICO)
        ItemPecaOS.objects.create(ordem_servico=os_, peca=self.peca, quantidade=quantidade)
        orcamento = Orcamento.em_aberto(os_)
        orcamento.enviar()
        orcamento.responder(aprovado=True)
        os_.refresh_from_db()
        return os_, orcamento

    def test_reservar_liberar_e_baixar(self):
        EstoqueService.reservar(self.peca, 4)
        EstoqueService.liberar(self.peca, 1)
        EstoqueService.baixar(self.peca, 3)
        self.peca.refresh_from_db()
        self.assertEqual((self.peca.quantidade, self.peca.quantidade_reservada), (7, 0))

    def test_reservar_acima_do_disponivel_levanta_validation_error(self):
        with self.assertRaises(ValidationError) as ctx:
            EstoqueService.reservar(self.peca, 11)
        self.assertEqual(
            ctx.exception.messages,
            ['Estoque insuficiente para "Filtro de óleo". Disponível: 10, solicitado: 11.'],
        )

    def test_alertar_reposicao_devolve_quantos_emails_sairam(self):
        self.peca.estoque_minimo = 20
        self.peca.save()
        self.assertEqual(EstoqueService.alertar_reposicao([self.peca]), 1)
        self.assertIn('mínimo', mail.outbox[0].subject.lower())

    def test_itens_da_os_liberar_e_baixar(self):
        os_, _ = self.aprovado(3)
        self.assertEqual(len(EstoqueService._itens_reservados(os_)), 1)
        EstoqueService.liberar_itens_os(os_)
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.quantidade_reservada, 0)

        os_, _ = self.aprovado(2)
        EstoqueService.baixar_itens_os(os_)
        self.peca.refresh_from_db()
        self.assertEqual((self.peca.quantidade, self.peca.quantidade_reservada), (8, 0))

    def test_reservar_itens_orcamento_e_tudo_ou_nada(self):
        os_ = self.criar_os(status=StatusOS.EM_DIAGNOSTICO)
        ItemPecaOS.objects.create(ordem_servico=os_, peca=self.peca, quantidade=50)
        orcamento = Orcamento.em_aberto(os_)
        with self.assertRaises(EstoqueInsuficiente) as ctx:
            EstoqueService.reservar_itens_orcamento(orcamento)
        self.assertIsInstance(ctx.exception, ValidationError)
        self.assertEqual(ctx.exception.faltantes[0]['solicitado'], 50)

        vazio = Orcamento.objects.create(ordem_servico=os_, sequencia=9)
        self.assertEqual(EstoqueService.reservar_itens_orcamento(vazio), [])


class FachadasDosModelsTests(OSTestCaseBase):
    def test_validar_transicao(self):
        OrdemServico.validar_transicao(StatusOS.RECEBIDA, StatusOS.EM_DIAGNOSTICO)
        with self.assertRaises(ValidationError) as ctx:
            OrdemServico.validar_transicao(StatusOS.RECEBIDA, StatusOS.ENTREGUE)
        self.assertIn('status', ctx.exception.message_dict)

    def test_itens_validar_sincronizar_e_reserva(self):
        os_ = self.criar_os(status=StatusOS.EM_DIAGNOSTICO)
        item = ItemPecaOS.objects.create(ordem_servico=os_, peca=self.peca, quantidade=2)
        item.refresh_from_db()
        self.assertFalse(item.esta_reservado)
        item.validar_proposta_em_avaliacao()

        servico = ItemServicoOS.objects.create(
            ordem_servico=os_, servico=self.servico, quantidade=1,
        )
        ItemServicoOS.objects.filter(pk=servico.pk).update(quantidade=3)
        servico.refresh_from_db()
        servico.sincronizar_orcamento()
        self.assertEqual(Orcamento.em_aberto(os_).valor_total, Decimal('530.00'))

        orcamento = Orcamento.em_aberto(os_)
        orcamento.enviar()
        item.refresh_from_db()
        with self.assertRaises(ValidationError):
            item.validar_proposta_em_avaliacao()

    def test_recalcular_total_e_descartar_itens(self):
        os_ = self.criar_os(status=StatusOS.EM_DIAGNOSTICO)
        ItemServicoOS.objects.create(ordem_servico=os_, servico=self.servico, quantidade=1)
        orcamento = Orcamento.em_aberto(os_)
        Orcamento.objects.filter(pk=orcamento.pk).update(valor_total=Decimal('1.00'))
        orcamento.refresh_from_db()
        self.assertIs(orcamento.recalcular_total(), orcamento)
        self.assertEqual(orcamento.valor_total, Decimal('150.00'))

        orcamento.descartar_itens()
        self.assertEqual(os_.itens_servico.count(), 0)
