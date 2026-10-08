import re

from oficina.erros import ErroDeDominio


class CpfCnpjInvalido(ErroDeDominio):
    pass


def somente_digitos(valor):
    return re.sub(r'\D', '', valor or '')


def _digito_cpf(digitos, pesos):
    soma = sum(int(d) * p for d, p in zip(digitos, pesos))
    resto = (soma * 10) % 11
    return 0 if resto == 10 else resto


def _digito_cnpj(digitos, pesos):
    soma = sum(int(d) * p for d, p in zip(digitos, pesos))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def validar_cpf_cnpj(valor):
    digitos = somente_digitos(valor)

    if len(digitos) == 11:
        if digitos == digitos[0] * 11:
            raise CpfCnpjInvalido('CPF inválido.')
        d1 = _digito_cpf(digitos[:9], range(10, 1, -1))
        d2 = _digito_cpf(digitos[:10], range(11, 1, -1))
        if digitos[9:] != f'{d1}{d2}':
            raise CpfCnpjInvalido('CPF inválido.')
    elif len(digitos) == 14:
        pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        pesos2 = [6] + pesos1
        d1 = _digito_cnpj(digitos[:12], pesos1)
        d2 = _digito_cnpj(digitos[:13], pesos2)
        if digitos[12:] != f'{d1}{d2}':
            raise CpfCnpjInvalido('CNPJ inválido.')
    else:
        raise CpfCnpjInvalido('Informe um CPF (11 dígitos) ou CNPJ (14 dígitos).')
