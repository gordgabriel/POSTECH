from datetime import datetime, timezone
from decimal import Decimal
from unittest import TestCase

from oficina.atendimento.dominio.erros import (
    EncerramentoInvalido,
    OrcamentoInvalido,
    PropostaEmAvaliacao,
    SemItensPendentes,
    TransicaoInvalida,
)
from oficina.atendimento.dominio.itens import (
    ajuste_de_reserva,
    esta_reservado,
    preco_congelado,
    validar_proposta_em_avaliacao,
)
from oficina.atendimento.dominio.orcamento import (
    Orcamento,
    StatusOrcamento,
    destino_apos_recusa,
    exigir_itens_pendentes,
    proxima_sequencia,
)
from oficina.atendimento.dominio.ordem_servico import (
    OrdemServico,
    StatusOS,
    veiculo_pertence_ao_cliente,
)

AGORA = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
DEPOIS = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


class StatusOSTests(TestCase):
    def test_compara_com_o_valor_gravado_no_banco(self):
        self.assertEqual(StatusOS.EM_EXECUCAO, 'EmExecucao')
        self.assertEqual(str(StatusOS.EM_EXECUCAO), 'EmExecucao')
        self.assertEqual(f'{StatusOS.EM_EXECUCAO}', 'EmExecucao')
        self.assertEqual(StatusOS.EM_EXECUCAO.label, 'Em execução')

    def test_rotulo_de_valor_desconhecido_volta_o_proprio_valor(self):
        self.assertEqual(StatusOS.rotulo_de('Entregue'), 'Entregue')
        self.assertEqual(StatusOS.rotulo_de('Outro'), 'Outro')


class OrdemServicoTests(TestCase):
    def nova(self, status=StatusOS.RECEBIDA, **kwargs):
        return OrdemServico(id=1, status=status, **kwargs)

    def test_fluxo_completo_carimba_as_datas(self):
        os_ = self.nova()
        for status in (
            StatusOS.EM_DIAGNOSTICO,
            StatusOS.AGUARDANDO_APROVACAO,
            StatusOS.EM_EXECUCAO,
            StatusOS.FINALIZADA,
            StatusOS.ENTREGUE,
        ):
            self.assertTrue(os_.transitar_para(status, AGORA))
        self.assertEqual(os_.status, StatusOS.ENTREGUE)
        self.assertEqual(
            os_.datas,
            {
                'data_diagnostico': AGORA,
                'data_inicio_execucao': AGORA,
                'data_finalizacao': AGORA,
                'data_entrega': AGORA,
            },
        )

    def test_transicao_invalida_tem_a_mensagem_da_api(self):
        os_ = self.nova()
        with self.assertRaises(TransicaoInvalida) as ctx:
            os_.transitar_para(StatusOS.FINALIZADA, AGORA)
        self.assertEqual(ctx.exception.campo, 'status')
        self.assertEqual(
            ctx.exception.mensagem,
            'Transição inválida: "Recebida" não pode ir para "Finalizada". '
            'Transições permitidas: [StatusOS.EM_DIAGNOSTICO].',
        )
        self.assertEqual(os_.status, StatusOS.RECEBIDA)

    def test_entregue_nao_vai_para_lugar_nenhum(self):
        with self.assertRaises(TransicaoInvalida) as ctx:
            self.nova(StatusOS.ENTREGUE).transitar_para(StatusOS.EM_DIAGNOSTICO, AGORA)
        self.assertIn('Transições permitidas: nenhuma.', ctx.exception.mensagem)

    def test_mesmo_status_nao_e_transicao(self):
        self.assertFalse(self.nova().transitar_para(StatusOS.RECEBIDA, AGORA))

    def test_reparo_adicional_nao_sobrescreve_o_inicio_da_execucao(self):
        os_ = self.nova(StatusOS.EM_EXECUCAO, datas={'data_inicio_execucao': AGORA})
        os_.transitar_para(StatusOS.AGUARDANDO_APROVACAO, DEPOIS)
        os_.transitar_para(StatusOS.EM_EXECUCAO, DEPOIS)
        self.assertEqual(os_.datas['data_inicio_execucao'], AGORA)

    def test_confirmar_mudanca_feita_direto_no_registro(self):
        os_ = self.nova(StatusOS.EM_DIAGNOSTICO)
        self.assertTrue(os_.confirmar_mudanca_de_status(StatusOS.RECEBIDA, AGORA))
        self.assertEqual(os_.datas['data_diagnostico'], AGORA)
        self.assertFalse(os_.confirmar_mudanca_de_status(None, AGORA))
        self.assertFalse(os_.confirmar_mudanca_de_status('EmDiagnostico', AGORA))
        with self.assertRaises(TransicaoInvalida):
            self.nova(StatusOS.FINALIZADA).confirmar_mudanca_de_status('Recebida', AGORA)

    def test_encerrar_nao_mexe_no_status(self):
        os_ = self.nova(StatusOS.EM_EXECUCAO)
        os_.encerrar()
        self.assertFalse(os_.is_active)
        self.assertEqual(os_.status, StatusOS.EM_EXECUCAO)

    def test_encerrar_duas_vezes_ou_entregue_e_rejeitado(self):
        with self.assertRaises(EncerramentoInvalido) as ctx:
            self.nova(is_active=False).encerrar()
        self.assertEqual(ctx.exception.campo, 'is_active')
        with self.assertRaises(EncerramentoInvalido):
            self.nova(StatusOS.ENTREGUE).encerrar()

    def test_veiculo_precisa_ser_do_cliente(self):
        self.assertTrue(veiculo_pertence_ao_cliente(5, 5))
        self.assertFalse(veiculo_pertence_ao_cliente(5, 6))


class OrcamentoTests(TestCase):
    def novo(self, **kwargs):
        return Orcamento(id=1, ordem_servico_id=1, sequencia=1, **kwargs)

    def test_total_e_a_soma_dos_itens(self):
        orcamento = self.novo()
        self.assertTrue(orcamento.atualizar_total([Decimal('150.00')], [Decimal('80.00')]))
        self.assertEqual(orcamento.valor_total, Decimal('230.00'))
        self.assertFalse(orcamento.atualizar_total([Decimal('150.00')], [Decimal('80.00')]))

    def test_enviar_registra_a_data_uma_vez(self):
        orcamento = self.novo()
        self.assertTrue(orcamento.enviar(StatusOS.EM_DIAGNOSTICO, AGORA))
        self.assertFalse(orcamento.enviar(StatusOS.EM_EXECUCAO, DEPOIS))
        self.assertEqual(orcamento.data_envio, AGORA)
        self.assertTrue(orcamento.aguardando_resposta)

    def test_enviar_exige_os_em_diagnostico_ou_execucao(self):
        with self.assertRaises(OrcamentoInvalido) as ctx:
            self.novo().enviar(StatusOS.RECEBIDA, AGORA)
        self.assertIn('com a OS em "Recebida"', ctx.exception.mensagem)

    def test_enviar_respondido_e_rejeitado(self):
        with self.assertRaises(OrcamentoInvalido) as ctx:
            self.novo(status=StatusOrcamento.APROVADO).enviar(StatusOS.EM_EXECUCAO, AGORA)
        self.assertEqual(
            ctx.exception.mensagem,
            'Só é possível enviar orçamento pendente (status atual: aprovado).',
        )

    def test_resposta_so_depois_do_envio(self):
        with self.assertRaises(OrcamentoInvalido) as ctx:
            self.novo().validar_resposta(StatusOS.EM_DIAGNOSTICO)
        self.assertIn('"Em diagnóstico"', ctx.exception.mensagem)
        with self.assertRaises(OrcamentoInvalido):
            self.novo(status=StatusOrcamento.RECUSADO).validar_resposta(
                StatusOS.AGUARDANDO_APROVACAO,
            )

    def test_registrar_resposta(self):
        orcamento = self.novo()
        orcamento.registrar_resposta(False, AGORA)
        self.assertEqual(orcamento.status, StatusOrcamento.RECUSADO)
        self.assertEqual(orcamento.data_resposta, AGORA)

    def test_destino_da_recusa_depende_de_ja_ter_autorizado(self):
        self.assertEqual(destino_apos_recusa(False), StatusOS.EM_DIAGNOSTICO)
        self.assertEqual(destino_apos_recusa(True), StatusOS.EM_EXECUCAO)

    def test_sequencia_e_itens_pendentes(self):
        self.assertEqual(proxima_sequencia(None), 1)
        self.assertEqual(proxima_sequencia(2), 3)
        with self.assertRaises(SemItensPendentes):
            exigir_itens_pendentes(False, None)
        exigir_itens_pendentes(False, self.novo())
        exigir_itens_pendentes(True, None)


class ItensTests(TestCase):
    def test_preco_congelado_so_consulta_o_catalogo_quando_falta(self):
        self.assertEqual(preco_congelado(Decimal('10'), lambda: 1 / 0), Decimal('10'))
        self.assertEqual(preco_congelado(None, lambda: Decimal('40')), Decimal('40'))

    def test_proposta_enviada_nao_e_alterada(self):
        validar_proposta_em_avaliacao(None)
        aberto = Orcamento(id=1, ordem_servico_id=1, sequencia=2)
        validar_proposta_em_avaliacao(aberto)
        aberto.data_envio = AGORA
        with self.assertRaises(PropostaEmAvaliacao) as ctx:
            validar_proposta_em_avaliacao(aberto)
        self.assertIn('O orçamento 2 está aguardando', ctx.exception.mensagem)

    def test_reserva_so_depois_da_aprovacao(self):
        self.assertFalse(esta_reservado(None))
        orcamento = Orcamento(id=1, ordem_servico_id=1, sequencia=1)
        self.assertFalse(esta_reservado(orcamento))
        orcamento.status = StatusOrcamento.APROVADO
        self.assertTrue(esta_reservado(orcamento))
        self.assertEqual(ajuste_de_reserva(2, 5), 3)
        self.assertEqual(ajuste_de_reserva(5, 2), -3)
