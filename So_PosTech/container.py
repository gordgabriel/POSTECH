"""Liga cada porta do núcleo (`oficina/`) ao seu adaptador Django."""
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone

from oficina.atendimento.casos_de_uso.criar_os import CriarOS
from oficina.atendimento.casos_de_uso.encerrar_os import EncerrarOS
from oficina.atendimento.casos_de_uso.enviar_orcamento import EnviarOrcamento
from oficina.atendimento.casos_de_uso.finalizar_os import FinalizarOS
from oficina.atendimento.casos_de_uso.gerar_orcamento import (
    GerarOrcamento,
    RecalcularOrcamento,
)
from oficina.atendimento.casos_de_uso.incluir_itens import (
    RemoverItem,
    SalvarItem,
    SincronizarOrcamento,
)
from oficina.atendimento.casos_de_uso.realizar_diagnostico import RealizarDiagnostico
from oficina.atendimento.casos_de_uso.registrar_entrega import RegistrarEntrega
from oficina.atendimento.casos_de_uso.responder_orcamento import ResponderOrcamento
from oficina.atendimento.casos_de_uso.transitar_os import EfeitosDaTransicao, TransitarOS
from oficina.estoque.casos_de_uso.alertar_reposicao import AlertarReposicao
from oficina.estoque.casos_de_uso.baixar import BaixarItens, BaixarPeca
from oficina.estoque.casos_de_uso.liberar import LiberarItens, LiberarPeca
from oficina.estoque.casos_de_uso.reservar import ReservarItensDoOrcamento, ReservarPeca
from oficina.portas import Relogio, UnidadeDeTrabalho


class UnidadeDeTrabalhoDjango(UnidadeDeTrabalho):
    def atomico(self):
        return transaction.atomic()

    def ao_confirmar(self, funcao):
        transaction.on_commit(funcao)


class RelogioDjango(Relogio):
    def agora(self):
        return timezone.now()


def estoque():
    from estoque.repositorios import PecaRepositorioDjango
    from notifications.adaptador import AlertaDeEstoqueEmail

    unidade = UnidadeDeTrabalhoDjango()
    pecas = PecaRepositorioDjango()
    alertar = AlertarReposicao(pecas, AlertaDeEstoqueEmail())
    reservar = ReservarPeca(pecas, unidade)
    liberar = LiberarPeca(pecas, unidade)
    baixar = BaixarPeca(pecas, unidade)
    return SimpleNamespace(
        reservar_peca=reservar,
        liberar_peca=liberar,
        baixar_peca=baixar,
        alertar_reposicao=alertar,
        reservar_itens=ReservarItensDoOrcamento(pecas, unidade, reservar, alertar),
        liberar_itens=LiberarItens(unidade, liberar),
        baixar_itens=BaixarItens(unidade, baixar, alertar),
    )


def atendimento(*instancias, gravacao=((), {})):
    # `instancias`: models que quem chama já tem; o caso de uso trabalha sobre eles.
    from notifications.adaptador import NotificadorEmail
    from so.repositorios import (
        ItemRepositorioDjango,
        MapaDeIdentidade,
        OrcamentoRepositorioDjango,
        OrdemServicoRepositorioDjango,
    )

    mapa = MapaDeIdentidade(instancias)
    unidade = UnidadeDeTrabalhoDjango()
    relogio = RelogioDjango()
    ordens = OrdemServicoRepositorioDjango(mapa)
    orcamentos = OrcamentoRepositorioDjango(mapa)
    itens = ItemRepositorioDjango(mapa, gravacao)
    notificador = NotificadorEmail(ordens.modelo)
    casos_estoque = estoque()

    transitar = TransitarOS(ordens, relogio)
    recalcular = RecalcularOrcamento(orcamentos, unidade)
    gerar = GerarOrcamento(orcamentos, unidade, recalcular)
    sincronizar = SincronizarOrcamento(orcamentos, gerar, recalcular)

    return SimpleNamespace(
        ordens=ordens,
        orcamentos=orcamentos,
        criar_os=CriarOS(ordens),
        transitar_os=transitar,
        efeitos_da_transicao=EfeitosDaTransicao(
            ordens, notificador, casos_estoque.baixar_itens,
        ),
        realizar_diagnostico=RealizarDiagnostico(ordens, relogio),
        finalizar_os=FinalizarOS(transitar),
        registrar_entrega=RegistrarEntrega(transitar),
        encerrar_os=EncerrarOS(ordens, notificador, casos_estoque.liberar_itens),
        gerar_orcamento=gerar,
        recalcular_orcamento=recalcular,
        sincronizar_orcamento=sincronizar,
        enviar_orcamento=EnviarOrcamento(orcamentos, ordens, transitar, relogio),
        responder_orcamento=ResponderOrcamento(
            orcamentos,
            ordens,
            transitar,
            casos_estoque.reservar_itens,
            notificador,
            relogio,
        ),
        salvar_item=SalvarItem(
            itens,
            orcamentos,
            unidade,
            sincronizar,
            casos_estoque.reservar_peca,
            casos_estoque.liberar_peca,
        ),
        remover_item=RemoverItem(itens, orcamentos, unidade, casos_estoque.liberar_peca),
    )
