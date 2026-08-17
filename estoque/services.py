from django.core.exceptions import ValidationError
from django.db import transaction

from estoque.models import Peca


class EstoqueService:
    """Reserva na inclusão do item, libera no cancelamento, baixa na entrega."""

    @staticmethod
    @transaction.atomic
    def reservar(peca, quantidade):
        peca = Peca.objects.select_for_update().get(pk=peca.pk)
        if peca.quantidade_disponivel < quantidade:
            raise ValidationError(
                f'Estoque insuficiente para "{peca.nome}". '
                f'Disponível: {peca.quantidade_disponivel}, '
                f'solicitado: {quantidade}.',
            )
        peca.quantidade_reservada += quantidade
        peca.save(update_fields=['quantidade_reservada', 'updated_at'])

    @staticmethod
    @transaction.atomic
    def liberar(peca, quantidade):
        peca = Peca.objects.select_for_update().get(pk=peca.pk)
        peca.quantidade_reservada = max(0, peca.quantidade_reservada - quantidade)
        peca.save(update_fields=['quantidade_reservada', 'updated_at'])

    @staticmethod
    @transaction.atomic
    def baixar(peca, quantidade):
        """Converte reserva em saída definitiva do estoque (entrega da OS)."""
        peca = Peca.objects.select_for_update().get(pk=peca.pk)
        peca.quantidade = max(0, peca.quantidade - quantidade)
        peca.quantidade_reservada = max(0, peca.quantidade_reservada - quantidade)
        peca.save(update_fields=['quantidade', 'quantidade_reservada', 'updated_at'])

    @classmethod
    @transaction.atomic
    def baixar_itens_os(cls, ordem_servico):
        for item in ordem_servico.itens_peca.select_related('peca'):
            cls.baixar(item.peca, item.quantidade)

    @classmethod
    @transaction.atomic
    def liberar_itens_os(cls, ordem_servico):
        for item in ordem_servico.itens_peca.select_related('peca'):
            cls.liberar(item.peca, item.quantidade)

    @classmethod
    @transaction.atomic
    def liberar_itens_orcamento(cls, orcamento):
        """Libera a reserva apenas das peças vinculadas a um orçamento."""
        for item in orcamento.itens_peca.select_related('peca'):
            cls.liberar(item.peca, item.quantidade)
