"""
Casos de uso rodando com portas falsas em memória.

É o ganho da arquitetura hexagonal: o fluxo da Ubíqua é testado sem banco,
sem HTTP e sem e-mail.
"""
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from unittest import TestCase

from oficina.atendimento.casos_de_uso.encerrar_os import EncerrarOS
from oficina.atendimento.casos_de_uso.enviar_orcamento import EnviarOrcamento
from oficina.atendimento.casos_de_uso.gerar_orcamento import (
    GerarOrcamento,
    RecalcularOrcamento,
)
from oficina.atendimento.casos_de_uso.responder_orcamento import ResponderOrcamento
from oficina.atendimento.casos_de_uso.transitar_os import EfeitosDaTransicao, TransitarOS
from oficina.atendimento.dominio.orcamento import Orcamento, StatusOrcamento
from oficina.atendimento.dominio.ordem_servico import OrdemServico, StatusOS
from oficina.estoque.casos_de_uso.alertar_reposicao import AlertarReposicao
from oficina.estoque.casos_de_uso.baixar import BaixarItens, BaixarPeca
from oficina.estoque.casos_de_uso.liberar import LiberarItens, LiberarPeca
from oficina.estoque.casos_de_uso.reservar import ReservarItensDoOrcamento, ReservarPeca
from oficina.estoque.dominio.erros import EstoqueInsuficiente
from oficina.estoque.dominio.peca import Peca

AGORA = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


class Relogio:
    def agora(self):
        return AGORA


class Unidade:
    def __init__(self):
        self.ao_confirmar_chamadas = []

    def atomico(self):
        return nullcontext()

    def ao_confirmar(self, funcao):
        self.ao_confirmar_chamadas.append(funcao)
        funcao()


class Oficina:
    """Estado em memória e todas as portas cumpridas sobre ele."""

    def __init__(self):
        self.ordens = {}
        self.orcamentos = {}
        self.itens = []  # dicts: os, orcamento, peca, quantidade, preco
        self.pecas = {}
        self.emails = []

    # --- OrdemServicoRepositorio
    def obter(self, os_id):
        return deepcopy(self.ordens[os_id])

    def salvar(self, entidade, campos=None):
        anterior = self.ordens[entidade.id].status
        self.ordens[entidade.id] = deepcopy(entidade)
        # Mesmo papel do save do adaptador: mudança gravada dispara efeitos.
        if anterior != entidade.status:
            self.efeitos.executar(entidade.id, entidade.status, anterior)

    def itens_peca_reservados(self, os_id):
        return [
            (i['peca'], i['quantidade'])
            for i in self.itens
            if i['os'] == os_id and i['peca'] and i['orcamento']
            and self.orcamentos[i['orcamento']].status == StatusOrcamento.APROVADO
        ]

    def possui_orcamento_aprovado(self, os_id):
        return any(
            o.ordem_servico_id == os_id and o.status == StatusOrcamento.APROVADO
            for o in self.orcamentos.values()
        )

    # --- Notificador e AlertaDeEstoque
    def status_alterado(self, os_id, anterior):
        self.emails.append(('status', os_id, str(self.ordens[os_id].status)))

    def os_encerrada(self, os_id):
        self.emails.append(('encerrada', os_id))

    def estoque_insuficiente(self, os_id, faltantes):
        self.emails.append(('insuficiente', os_id, [f['peca'].nome for f in faltantes]))

    def estoque_minimo(self, pecas):
        abaixo = [p.nome for p in pecas if p.abaixo_do_minimo]
        if abaixo:
            self.emails.append(('minimo', abaixo))
        return len(abaixo)


class Orcamentos:
    def __init__(self, oficina):
        self.o = oficina

    def obter(self, orcamento_id):
        return deepcopy(self.o.orcamentos[orcamento_id])

    def em_aberto(self, os_id):
        for orcamento in self.o.orcamentos.values():
            if orcamento.ordem_servico_id == os_id and orcamento.em_aberto:
                return deepcopy(orcamento)
        return None

    def ha_itens_pendentes(self, os_id):
        return any(i['os'] == os_id and i['orcamento'] is None for i in self.o.itens)

    def ultima_sequencia(self, os_id):
        sequencias = [
            o.sequencia for o in self.o.orcamentos.values() if o.ordem_servico_id == os_id
        ]
        return max(sequencias) if sequencias else None

    def criar(self, os_id, sequencia):
        novo = Orcamento(id=len(self.o.orcamentos) + 1, ordem_servico_id=os_id, sequencia=sequencia)
        self.o.orcamentos[novo.id] = novo
        return deepcopy(novo)

    def vincular_itens_pendentes(self, os_id, orcamento_id):
        for item in self.o.itens:
            if item['os'] == os_id and item['orcamento'] is None:
                item['orcamento'] = orcamento_id

    def subtotais(self, orcamento_id):
        def subtotais(de_peca):
            return [
                i['quantidade'] * i['preco']
                for i in self.o.itens
                if i['orcamento'] == orcamento_id and bool(i['peca']) == de_peca
            ]
        return subtotais(False), subtotais(True)

    def itens_peca(self, orcamento_id):
        return [
            (i['peca'], i['quantidade'])
            for i in self.o.itens
            if i['orcamento'] == orcamento_id and i['peca']
        ]

    def salvar(self, orcamento, campos):
        self.o.orcamentos[orcamento.id] = deepcopy(orcamento)

    def descartar_itens(self, orcamento_id):
        self.o.itens = [i for i in self.o.itens if i['orcamento'] != orcamento_id]


class Pecas:
    def __init__(self, oficina):
        self.o = oficina

    def travar(self, peca_id):
        return deepcopy(self.o.pecas[peca_id])

    def travar_varias(self, ids):
        return [deepcopy(self.o.pecas[i]) for i in ids]

    obter_varias = travar_varias

    def salvar(self, peca, campos):
        self.o.pecas[peca.id] = deepcopy(peca)


class CasosDeUsoTests(TestCase):
    def setUp(self):
        self.oficina = o = Oficina()
        unidade = Unidade()
        pecas = Pecas(o)
        orcamentos = Orcamentos(o)
        alertar = AlertarReposicao(pecas, o)
        reservar = ReservarPeca(pecas, unidade)
        liberar = LiberarPeca(pecas, unidade)
        baixar = BaixarPeca(pecas, unidade)
        o.efeitos = EfeitosDaTransicao(o, o, BaixarItens(unidade, baixar, alertar))
        transitar = TransitarOS(o, Relogio())
        recalcular = RecalcularOrcamento(orcamentos, unidade)
        self.gerar = GerarOrcamento(orcamentos, unidade, recalcular)
        self.enviar = EnviarOrcamento(orcamentos, o, transitar, Relogio())
        self.responder = ResponderOrcamento(
            orcamentos, o, transitar,
            ReservarItensDoOrcamento(pecas, unidade, reservar, alertar),
            o, Relogio(),
        )
        self.transitar = transitar
        self.encerrar = EncerrarOS(o, o, LiberarItens(unidade, liberar))

        o.pecas[1] = Peca(id=1, nome='Filtro', quantidade=10, quantidade_reservada=0, estoque_minimo=8)
        o.pecas[2] = Peca(id=2, nome='Pastilha', quantidade=1, quantidade_reservada=0)
        o.ordens[1] = OrdemServico(id=1, status=StatusOS.EM_DIAGNOSTICO)

    def incluir(self, peca=None, quantidade=1, preco=Decimal('40.00')):
        self.oficina.itens.append(
            {'os': 1, 'orcamento': None, 'peca': peca, 'quantidade': quantidade, 'preco': preco},
        )

    def test_gerar_enviar_e_aprovar_reserva_e_inicia_a_execucao(self):
        self.incluir(quantidade=1, preco=Decimal('150.00'))
        self.incluir(peca=1, quantidade=3)
        orcamento = self.gerar.executar(1)
        self.assertEqual((orcamento.sequencia, orcamento.valor_total), (1, Decimal('270.00')))

        self.enviar.executar(orcamento.id)
        self.assertEqual(self.oficina.ordens[1].status, StatusOS.AGUARDANDO_APROVACAO)

        self.responder.executar(orcamento.id, aprovado=True)
        self.assertEqual(self.oficina.ordens[1].status, StatusOS.EM_EXECUCAO)
        self.assertEqual(self.oficina.pecas[1].quantidade_reservada, 3)
        self.assertIn(('minimo', ['Filtro']), self.oficina.emails)

    def test_falta_de_estoque_avisa_e_nao_grava_a_resposta(self):
        self.incluir(peca=1, quantidade=2)
        self.incluir(peca=2, quantidade=5)
        orcamento = self.gerar.executar(1)
        self.enviar.executar(orcamento.id)

        with self.assertRaises(EstoqueInsuficiente):
            self.responder.executar(orcamento.id, aprovado=True)

        self.assertEqual(self.oficina.orcamentos[orcamento.id].status, StatusOrcamento.PENDENTE)
        self.assertEqual(self.oficina.pecas[1].quantidade_reservada, 0)
        self.assertEqual(self.oficina.ordens[1].status, StatusOS.AGUARDANDO_APROVACAO)
        self.assertIn(('insuficiente', 1, ['Pastilha']), self.oficina.emails)

    def test_recusa_inicial_descarta_os_itens_e_volta_para_diagnostico(self):
        self.incluir(peca=1, quantidade=2)
        orcamento = self.gerar.executar(1)
        self.enviar.executar(orcamento.id)
        self.responder.executar(orcamento.id, aprovado=False)

        self.assertEqual(self.oficina.ordens[1].status, StatusOS.EM_DIAGNOSTICO)
        self.assertEqual(self.oficina.itens, [])
        self.incluir(quantidade=1)
        self.assertEqual(self.gerar.executar(1).sequencia, 2)

    def test_entrega_baixa_o_estoque_e_encerrar_libera(self):
        self.incluir(peca=1, quantidade=2)
        orcamento = self.gerar.executar(1)
        self.enviar.executar(orcamento.id)
        self.responder.executar(orcamento.id, aprovado=True)

        self.transitar.executar(1, StatusOS.FINALIZADA)
        self.transitar.executar(1, StatusOS.ENTREGUE)
        self.assertEqual(
            (self.oficina.pecas[1].quantidade, self.oficina.pecas[1].quantidade_reservada),
            (8, 0),
        )

        self.oficina.ordens[2] = OrdemServico(id=2, status=StatusOS.EM_EXECUCAO)
        self.oficina.orcamentos[99] = Orcamento(
            id=99, ordem_servico_id=2, sequencia=1, status=StatusOrcamento.APROVADO,
        )
        self.oficina.itens.append(
            {'os': 2, 'orcamento': 99, 'peca': 1, 'quantidade': 3, 'preco': Decimal('1')},
        )
        self.oficina.pecas[1].quantidade_reservada = 3
        self.encerrar.executar(2)
        self.assertFalse(self.oficina.ordens[2].is_active)
        self.assertEqual(self.oficina.ordens[2].status, StatusOS.EM_EXECUCAO)
        self.assertEqual(self.oficina.pecas[1].quantidade_reservada, 0)
        self.assertIn(('encerrada', 2), self.oficina.emails)
