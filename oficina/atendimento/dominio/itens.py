from dataclasses import dataclass

from oficina.atendimento.dominio.erros import PropostaEmAvaliacao


@dataclass
class ItemOS:
    id: object
    ordem_servico_id: object
    orcamento_id: object
    quantidade: int
    preco_unitario: object
    peca_id: object = None
    catalogo: str = 'servico'

    @property
    def eh_peca(self):
        return self.catalogo == 'peca'

    @property
    def novo(self):
        return self.id is None


def subtotal(quantidade, preco_unitario):
    return quantidade * preco_unitario


def preco_congelado(preco_unitario, preco_do_catalogo):
    if preco_unitario is None:
        return preco_do_catalogo()
    return preco_unitario


def validar_proposta_em_avaliacao(orcamento):
    if orcamento is None:
        return
    if orcamento.aguardando_resposta:
        raise PropostaEmAvaliacao(
            f'O orçamento {orcamento.sequencia} está aguardando a '
            f'resposta do cliente e não pode ser alterado. Registre a '
            f'recusa para remontar a proposta.',
        )


def esta_reservado(orcamento):
    # A peça só segura estoque depois da aprovação.
    return orcamento is not None and orcamento.aprovado


def ajuste_de_reserva(quantidade_anterior, quantidade_nova):
    return quantidade_nova - quantidade_anterior
