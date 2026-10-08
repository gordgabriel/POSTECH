from unittest import TestCase

from oficina.cadastros.dominio.cpf_cnpj import CpfCnpjInvalido, validar_cpf_cnpj
from oficina.cadastros.dominio.placa import PlacaInvalida, normalizar_placa, validar_placa
from oficina.estoque.dominio.erros import EstoqueInsuficiente, SaldoInsuficiente
from oficina.estoque.dominio.peca import Peca, conferir_saldo, somar_necessario


def peca(id_=1, quantidade=10, reservada=0, minimo=0, nome='Filtro'):
    return Peca(
        id=id_,
        nome=nome,
        quantidade=quantidade,
        quantidade_reservada=reservada,
        estoque_minimo=minimo,
    )


class PecaTests(TestCase):
    def test_disponivel_desconta_a_reserva(self):
        filtro = peca(quantidade=10, reservada=3, minimo=8)
        self.assertEqual(filtro.quantidade_disponivel, 7)
        self.assertTrue(filtro.abaixo_do_minimo)

    def test_reservar_acima_do_disponivel(self):
        with self.assertRaises(SaldoInsuficiente) as ctx:
            peca(quantidade=2).reservar(3)
        self.assertEqual(
            ctx.exception.mensagem,
            'Estoque insuficiente para "Filtro". Disponível: 2, solicitado: 3.',
        )

    def test_reservar_liberar_e_baixar(self):
        filtro = peca(quantidade=10)
        filtro.reservar(4)
        filtro.liberar(1)
        self.assertEqual(filtro.quantidade_reservada, 3)
        filtro.baixar(3)
        self.assertEqual((filtro.quantidade, filtro.quantidade_reservada), (7, 0))
        filtro.liberar(50)
        filtro.baixar(50)
        self.assertEqual((filtro.quantidade, filtro.quantidade_reservada), (0, 0))

    def test_reserva_e_tudo_ou_nada(self):
        necessario = somar_necessario([(1, 2), (2, 9), (1, 3)])
        self.assertEqual(necessario, {1: 5, 2: 9})
        with self.assertRaises(EstoqueInsuficiente) as ctx:
            conferir_saldo([peca(1, 10), peca(2, 4, nome='Pastilha')], necessario)
        self.assertEqual(
            ctx.exception.mensagem,
            'Estoque insuficiente para Pastilha: precisa de 9, disponível 4.',
        )
        self.assertEqual(ctx.exception.faltantes[0]['solicitado'], 9)
        conferir_saldo([peca(1, 10), peca(2, 9)], necessario)


class CadastrosTests(TestCase):
    def test_cpf_e_cnpj(self):
        validar_cpf_cnpj('529.982.247-25')
        validar_cpf_cnpj('11.444.777/0001-61')
        for invalido, mensagem in (
            ('111.111.111-11', 'CPF inválido.'),
            ('529.982.247-26', 'CPF inválido.'),
            ('11.444.777/0001-62', 'CNPJ inválido.'),
            ('123', 'Informe um CPF (11 dígitos) ou CNPJ (14 dígitos).'),
        ):
            with self.assertRaises(CpfCnpjInvalido) as ctx:
                validar_cpf_cnpj(invalido)
            self.assertEqual(ctx.exception.mensagem, mensagem)

    def test_placa(self):
        validar_placa('ABC1234')
        validar_placa('abc1d23')
        validar_placa('ABC-1234')
        with self.assertRaises(PlacaInvalida):
            validar_placa('AB12345')
        self.assertEqual(normalizar_placa('abc-1d23'), 'ABC1D23')
