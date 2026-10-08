"""Adaptador ORM das portas do Atendimento."""
from django.db import models, transaction

from oficina.atendimento.dominio.itens import ItemOS
from oficina.atendimento.dominio.orcamento import Orcamento, StatusOrcamento
from oficina.atendimento.dominio.ordem_servico import OrdemServico, StatusOS
from oficina.atendimento.portas.repositorios import (
    ItemRepositorio,
    OrcamentoRepositorio,
    OrdemServicoRepositorio,
)
from so.models import ItemPecaOS, ItemServicoOS
from so.models import Orcamento as OrcamentoModel
from so.models import OrdemServico as OrdemServicoModel
from so.models import StatusOS as StatusOSModel

CAMPOS_DATA = ['data_diagnostico', 'data_inicio_execucao', 'data_finalizacao', 'data_entrega']


class MapaDeIdentidade:
    # Reaproveita as instâncias que quem chamou já tem, para ela ver o objeto atualizado.
    RELACOES = ('ordem_servico', 'orcamento')

    def __init__(self, instancias=()):
        self._origens = [i for i in instancias if i is not None]
        self._registros = {}
        for instancia in self._origens:
            self.registrar(instancia)

    def registrar(self, instancia):
        self._registros[(type(instancia), instancia.pk)] = instancia
        return instancia

    def obter(self, modelo, pk):
        chave = (modelo, pk)
        if chave in self._registros:
            return self._registros[chave]
        relacionada = self._pela_relacao(modelo, pk)
        if relacionada is not None:
            return self.registrar(relacionada)
        return self.registrar(modelo.objects.get(pk=pk))

    def _pela_relacao(self, modelo, pk):
        for origem in self._origens:
            for nome in self.RELACOES:
                descritor = getattr(type(origem), nome, None)
                campo = getattr(descritor, 'field', None)
                if campo is None or campo.related_model is not modelo:
                    continue
                if getattr(origem, campo.attname) == pk:
                    return getattr(origem, nome)
        return None


def _status_do_model(valor, enum_dominio, enum_model):
    if isinstance(valor, enum_dominio):
        return enum_model(valor.value)
    return valor


class OrdemServicoRepositorioDjango(OrdemServicoRepositorio):
    def __init__(self, mapa):
        self.mapa = mapa

    def modelo(self, os_id):
        return self.mapa.obter(OrdemServicoModel, os_id)

    @staticmethod
    def para_entidade(modelo):
        return OrdemServico(
            id=modelo.pk,
            status=modelo.status,
            diagnostico=modelo.diagnostico,
            is_active=modelo.is_active,
            datas={campo: getattr(modelo, campo) for campo in CAMPOS_DATA},
        )

    @staticmethod
    def aplicar(entidade, modelo):
        if entidade.status is not modelo.status:
            modelo.status = _status_do_model(entidade.status, StatusOS, StatusOSModel)
        if entidade.diagnostico is not modelo.diagnostico:
            modelo.diagnostico = entidade.diagnostico
        modelo.is_active = entidade.is_active
        for campo in CAMPOS_DATA:
            if entidade.datas.get(campo) is not getattr(modelo, campo):
                setattr(modelo, campo, entidade.datas.get(campo))

    def criar(self, dados):
        return OrdemServicoModel.objects.create(**dados)

    def obter(self, os_id):
        return self.para_entidade(self.modelo(os_id))

    def salvar(self, ordem_servico, campos=None):
        modelo = self.modelo(ordem_servico.id)
        self.aplicar(ordem_servico, modelo)
        if campos is None:
            modelo.save()
        else:
            modelo.save(update_fields=[*campos, 'updated_at'])

    def itens_peca_reservados(self, os_id):
        itens = self.modelo(os_id).itens_peca.select_related('peca').filter(
            orcamento__status=OrcamentoModel.Status.APROVADO,
        )
        return [(item.peca_id, item.quantidade) for item in itens]

    def possui_orcamento_aprovado(self, os_id):
        return self.modelo(os_id).orcamentos.filter(
            status=OrcamentoModel.Status.APROVADO,
        ).exists()


class OrcamentoRepositorioDjango(OrcamentoRepositorio):
    def __init__(self, mapa):
        self.mapa = mapa

    def modelo(self, orcamento_id):
        return self.mapa.obter(OrcamentoModel, orcamento_id)

    def _os(self, os_id):
        return self.mapa.obter(OrdemServicoModel, os_id)

    @staticmethod
    def para_entidade(modelo):
        return Orcamento(
            id=modelo.pk,
            ordem_servico_id=modelo.ordem_servico_id,
            sequencia=modelo.sequencia,
            status=modelo.status,
            valor_total=modelo.valor_total,
            data_envio=modelo.data_envio,
            data_resposta=modelo.data_resposta,
        )

    @staticmethod
    def aplicar(entidade, modelo):
        if entidade.status is not modelo.status:
            modelo.status = _status_do_model(
                entidade.status, StatusOrcamento, OrcamentoModel.Status,
            )
        modelo.valor_total = entidade.valor_total
        modelo.data_envio = entidade.data_envio
        modelo.data_resposta = entidade.data_resposta

    def obter(self, orcamento_id):
        return self.para_entidade(self.modelo(orcamento_id))

    def em_aberto(self, os_id):
        modelo = OrcamentoModel.em_aberto(self._os(os_id))
        if modelo is None:
            return None
        return self.para_entidade(self.mapa.registrar(modelo))

    def ha_itens_pendentes(self, os_id):
        ordem_servico = self._os(os_id)
        return (
            ordem_servico.itens_servico.filter(orcamento__isnull=True).exists()
            or ordem_servico.itens_peca.filter(orcamento__isnull=True).exists()
        )

    def ultima_sequencia(self, os_id):
        return self._os(os_id).orcamentos.aggregate(
            models.Max('sequencia'),
        )['sequencia__max']

    def criar(self, os_id, sequencia):
        modelo = OrcamentoModel.objects.create(
            ordem_servico=self._os(os_id),
            sequencia=sequencia,
        )
        return self.para_entidade(self.mapa.registrar(modelo))

    def vincular_itens_pendentes(self, os_id, orcamento_id):
        ordem_servico = self._os(os_id)
        orcamento = self.modelo(orcamento_id)
        ordem_servico.itens_servico.filter(orcamento__isnull=True).update(orcamento=orcamento)
        ordem_servico.itens_peca.filter(orcamento__isnull=True).update(orcamento=orcamento)

    def subtotais(self, orcamento_id):
        orcamento = self.modelo(orcamento_id)
        return (
            [item.subtotal for item in orcamento.itens_servico.all()],
            [item.subtotal for item in orcamento.itens_peca.all()],
        )

    def itens_peca(self, orcamento_id):
        itens = self.modelo(orcamento_id).itens_peca.select_related('peca')
        return [(item.peca_id, item.quantidade) for item in itens]

    def salvar(self, orcamento, campos):
        modelo = self.modelo(orcamento.id)
        self.aplicar(orcamento, modelo)
        modelo.save(update_fields=campos)

    def descartar_itens(self, orcamento_id):
        orcamento = self.modelo(orcamento_id)
        with transaction.atomic():
            for item in list(orcamento.itens_peca.all()) + list(orcamento.itens_servico.all()):
                item.delete()


class ItemRepositorioDjango(ItemRepositorio):
    def __init__(self, mapa, gravacao=((), {})):
        self.mapa = mapa
        self.args, self.kwargs = gravacao

    @staticmethod
    def para_entidade(modelo):
        eh_peca = isinstance(modelo, ItemPecaOS)
        return ItemOS(
            id=modelo.pk,
            ordem_servico_id=modelo.ordem_servico_id,
            orcamento_id=modelo.orcamento_id,
            quantidade=modelo.quantidade,
            preco_unitario=modelo.preco_unitario,
            peca_id=modelo.peca_id if eh_peca else None,
            catalogo='peca' if eh_peca else 'servico',
        )

    def _modelo(self, item):
        classe = ItemPecaOS if item.eh_peca else ItemServicoOS
        return self.mapa.obter(classe, item.id)

    def preco_de_catalogo(self, item):
        modelo = self._modelo(item)
        return modelo.peca.preco if item.eh_peca else modelo.servico.preco

    def quantidade_gravada(self, item_id):
        return ItemPecaOS.objects.get(pk=item_id).quantidade

    def gravar(self, item):
        modelo = self._modelo(item)
        if item.preco_unitario is not modelo.preco_unitario:
            modelo.preco_unitario = item.preco_unitario
        # Grava sem passar de novo pelo save do model, que é quem chamou.
        models.Model.save(modelo, *self.args, **self.kwargs)

    def remover(self, item):
        return models.Model.delete(self._modelo(item), *self.args, **self.kwargs)
