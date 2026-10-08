import uuid

from django.db import models

from oficina.atendimento.dominio import itens as dominio
from So_PosTech.exceptions import traduzir_erros_de_dominio


class ItemOSBase(models.Model):
    """Campos comuns aos itens de serviço e de peça da OS."""

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    quantidade = models.PositiveIntegerField(default=1)
    # Congelado na inclusão: reajuste no catálogo não muda valor já aprovado.
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

    @property
    def subtotal(self):
        return dominio.subtotal(self.quantidade, self.preco_unitario)

    def _casos(self, *args, **kwargs):
        from So_PosTech.container import atendimento

        return atendimento(self, gravacao=(args, kwargs))

    def _entidade(self):
        from so.repositorios import ItemRepositorioDjango

        return ItemRepositorioDjango.para_entidade(self)

    def _orcamento(self, casos):
        if self.orcamento_id is None:
            return None
        return casos.orcamentos.obter(self.orcamento_id)

    def validar_proposta_em_avaliacao(self):
        with traduzir_erros_de_dominio():
            dominio.validar_proposta_em_avaliacao(self._orcamento(self._casos()))

    def sincronizar_orcamento(self):
        with traduzir_erros_de_dominio():
            self._casos().sincronizar_orcamento.executar(self._entidade())

    def save(self, *args, **kwargs):
        with traduzir_erros_de_dominio():
            self._casos(*args, **kwargs).salvar_item.executar(self._entidade())

    def delete(self, *args, **kwargs):
        with traduzir_erros_de_dominio():
            return self._casos(*args, **kwargs).remover_item.executar(self._entidade())
