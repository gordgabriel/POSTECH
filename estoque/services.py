from django.core.exceptions import ValidationError

from So_PosTech.exceptions import traduzir_erros_de_dominio


class EstoqueInsuficiente(ValidationError):
    def __init__(self, faltantes):
        self.faltantes = faltantes
        detalhe = '; '.join(
            f'{f["peca"].nome}: precisa de {f["solicitado"]}, '
            f'disponível {f["disponivel"]}'
            for f in faltantes
        )
        super().__init__(f'Estoque insuficiente para {detalhe}.')


def _estoque():
    from So_PosTech.container import estoque

    return estoque()


def _itens(queryset):
    return [(item.peca_id, item.quantidade) for item in queryset]


class EstoqueService:
    """Fachada dos casos de uso de estoque (oficina/estoque)."""

    @staticmethod
    def reservar(peca, quantidade):
        with traduzir_erros_de_dominio():
            _estoque().reservar_peca.executar(peca.pk, quantidade)

    @staticmethod
    def liberar(peca, quantidade):
        _estoque().liberar_peca.executar(peca.pk, quantidade)

    @staticmethod
    def baixar(peca, quantidade):
        _estoque().baixar_peca.executar(peca.pk, quantidade)

    @staticmethod
    def alertar_reposicao(pecas):
        return _estoque().alertar_reposicao.executar([p.pk for p in pecas])

    @staticmethod
    def _itens_reservados(ordem_servico):
        from so.models.orcamento import Orcamento

        return ordem_servico.itens_peca.select_related('peca').filter(
            orcamento__status=Orcamento.Status.APROVADO,
        )

    @classmethod
    def baixar_itens_os(cls, ordem_servico):
        _estoque().baixar_itens.executar(_itens(cls._itens_reservados(ordem_servico)))

    @classmethod
    def liberar_itens_os(cls, ordem_servico):
        _estoque().liberar_itens.executar(_itens(cls._itens_reservados(ordem_servico)))

    @classmethod
    def reservar_itens_orcamento(cls, orcamento):
        itens = list(orcamento.itens_peca.select_related('peca'))
        with traduzir_erros_de_dominio():
            _estoque().reservar_itens.executar(_itens(itens))
        return itens
