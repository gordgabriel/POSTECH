from django.core.exceptions import ValidationError
from django.db import transaction

from estoque.models import Peca


class EstoqueInsuficiente(ValidationError):
    """Falta peça para atender o orçamento. Carrega o que faltou, por peça."""

    def __init__(self, faltantes):
        self.faltantes = faltantes
        detalhe = '; '.join(
            f'{f["peca"].nome}: precisa de {f["solicitado"]}, '
            f'disponível {f["disponivel"]}'
            for f in faltantes
        )
        super().__init__(f'Estoque insuficiente para {detalhe}.')


class EstoqueService:
    """Reserva na aprovação do orçamento, libera no cancelamento, baixa na entrega."""

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

    @staticmethod
    def alertar_reposicao(pecas):
        """Política: estoque abaixo do mínimo, então alertar reposição."""
        from notifications.services.estoque_notifications import alertar_estoque_minimo

        atualizadas = Peca.objects.filter(pk__in=[p.pk for p in pecas])
        return alertar_estoque_minimo(atualizadas)

    @staticmethod
    def _itens_reservados(ordem_servico):
        """
        Só os itens de orçamento aprovado seguram estoque.

        Baixar ou liberar um item não aprovado mexeria numa reserva que nunca
        existiu — e, como o saldo reservado é por peça, roubaria a reserva de
        outra OS que usa a mesma peça.
        """
        from so.models.orcamento import Orcamento

        return ordem_servico.itens_peca.select_related('peca').filter(
            orcamento__status=Orcamento.Status.APROVADO,
        )

    @classmethod
    @transaction.atomic
    def baixar_itens_os(cls, ordem_servico):
        itens = list(cls._itens_reservados(ordem_servico))
        for item in itens:
            cls.baixar(item.peca, item.quantidade)
        transaction.on_commit(
            lambda: cls.alertar_reposicao([i.peca for i in itens]),
        )

    @classmethod
    @transaction.atomic
    def liberar_itens_os(cls, ordem_servico):
        for item in cls._itens_reservados(ordem_servico):
            cls.liberar(item.peca, item.quantidade)

    @classmethod
    @transaction.atomic
    def reservar_itens_orcamento(cls, orcamento):
        """
        Reserva todas as peças do orçamento de uma vez.

        Confere o saldo de todas antes de reservar qualquer uma: ou o orçamento
        inteiro é atendido, ou nada é reservado e o chamador fica sabendo o que
        faltou. Peça repetida em itens diferentes soma na conferência.
        """
        itens = list(orcamento.itens_peca.select_related('peca'))
        if not itens:
            return []

        necessario = {}
        for item in itens:
            necessario[item.peca_id] = necessario.get(item.peca_id, 0) + item.quantidade

        travadas = Peca.objects.select_for_update().filter(pk__in=necessario)
        faltantes = [
            {
                'peca': peca,
                'solicitado': necessario[peca.pk],
                'disponivel': peca.quantidade_disponivel,
            }
            for peca in travadas
            if peca.quantidade_disponivel < necessario[peca.pk]
        ]
        if faltantes:
            raise EstoqueInsuficiente(faltantes)

        for item in itens:
            cls.reservar(item.peca, item.quantidade)
        # A reserva derruba o disponível, então é aqui que o mínimo é furado.
        transaction.on_commit(
            lambda: cls.alertar_reposicao([i.peca for i in itens]),
        )
        return itens
