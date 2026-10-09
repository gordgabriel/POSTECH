import re

from oficina.erros import ErroDeDominio

# Padrão antigo (ABC1234) ou Mercosul (ABC1D23).
PLACA_REGEX = re.compile(r'^[A-Z]{3}-?\d[A-Z0-9]\d{2}$')


class PlacaInvalida(ErroDeDominio):
    pass


def validar_placa(valor):
    if not PLACA_REGEX.match((valor or '').upper()):
        raise PlacaInvalida('Placa inválida. Use o formato ABC1234 ou ABC1D23.')


def normalizar_placa(valor):
    return valor.upper().replace('-', '')
