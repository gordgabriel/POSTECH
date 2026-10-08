from dataclasses import dataclass

from oficina.estoque.dominio.erros import EstoqueInsuficiente, SaldoInsuficiente


def calcular_disponivel(quantidade, quantidade_reservada):
    return quantidade - quantidade_reservada


def esta_abaixo_do_minimo(quantidade_disponivel, estoque_minimo):
    return quantidade_disponivel < estoque_minimo


@dataclass
class Peca:
    id: object
    nome: str
    quantidade: int
    quantidade_reservada: int
    estoque_minimo: int = 0

    @property
    def quantidade_disponivel(self):
        return calcular_disponivel(self.quantidade, self.quantidade_reservada)

    @property
    def abaixo_do_minimo(self):
        return esta_abaixo_do_minimo(self.quantidade_disponivel, self.estoque_minimo)

    def reservar(self, quantidade):
        if self.quantidade_disponivel < quantidade:
            raise SaldoInsuficiente(
                f'Estoque insuficiente para "{self.nome}". '
                f'Disponível: {self.quantidade_disponivel}, '
                f'solicitado: {quantidade}.',
            )
        self.quantidade_reservada += quantidade

    def liberar(self, quantidade):
        self.quantidade_reservada = max(0, self.quantidade_reservada - quantidade)

    def baixar(self, quantidade):
        self.quantidade = max(0, self.quantidade - quantidade)
        self.quantidade_reservada = max(0, self.quantidade_reservada - quantidade)


def somar_necessario(itens):
    necessario = {}
    for peca_id, quantidade in itens:
        necessario[peca_id] = necessario.get(peca_id, 0) + quantidade
    return necessario


def conferir_saldo(pecas, necessario):
    # Tudo ou nada: se faltar qualquer peça, nenhuma é reservada.
    faltantes = [
        {
            'peca': peca,
            'solicitado': necessario[peca.id],
            'disponivel': peca.quantidade_disponivel,
        }
        for peca in pecas
        if peca.quantidade_disponivel < necessario[peca.id]
    ]
    if faltantes:
        raise EstoqueInsuficiente(faltantes)
