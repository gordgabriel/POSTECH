"""Validações dos value objects CpfCnpj e Placa (Linguagem Ubíqua)."""
import re

from django.core.exceptions import ValidationError

PLACA_REGEX = re.compile(r'^[A-Z]{3}-?\d[A-Z0-9]\d{2}$')


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
    """Aceita CPF (11 dígitos) ou CNPJ (14 dígitos), com ou sem máscara."""
    digitos = somente_digitos(valor)

    if len(digitos) == 11:
        if digitos == digitos[0] * 11:
            raise ValidationError('CPF inválido.')
        d1 = _digito_cpf(digitos[:9], range(10, 1, -1))
        d2 = _digito_cpf(digitos[:10], range(11, 1, -1))
        if digitos[9:] != f'{d1}{d2}':
            raise ValidationError('CPF inválido.')
    elif len(digitos) == 14:
        pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        pesos2 = [6] + pesos1
        d1 = _digito_cnpj(digitos[:12], pesos1)
        d2 = _digito_cnpj(digitos[:13], pesos2)
        if digitos[12:] != f'{d1}{d2}':
            raise ValidationError('CNPJ inválido.')
    else:
        raise ValidationError('Informe um CPF (11 dígitos) ou CNPJ (14 dígitos).')


def validar_placa(valor):
    """Aceita placa no padrão antigo (ABC1234) ou Mercosul (ABC1D23)."""
    if not PLACA_REGEX.match((valor or '').upper()):
        raise ValidationError('Placa inválida. Use o formato ABC1234 ou ABC1D23.')
