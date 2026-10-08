from oficina.erros import ErroDeDominio


class SaldoInsuficiente(ErroDeDominio):
    pass


class EstoqueInsuficiente(ErroDeDominio):
    def __init__(self, faltantes):
        self.faltantes = faltantes
        detalhe = '; '.join(
            f'{f["peca"].nome}: precisa de {f["solicitado"]}, '
            f'disponível {f["disponivel"]}'
            for f in faltantes
        )
        super().__init__(f'Estoque insuficiente para {detalhe}.')
