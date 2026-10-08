from oficina.cadastros.dominio import cpf_cnpj, placa
from So_PosTech.exceptions import traduzir_erros_de_dominio

PLACA_REGEX = placa.PLACA_REGEX
somente_digitos = cpf_cnpj.somente_digitos


def validar_cpf_cnpj(valor):
    with traduzir_erros_de_dominio():
        cpf_cnpj.validar_cpf_cnpj(valor)


def validar_placa(valor):
    with traduzir_erros_de_dominio():
        placa.validar_placa(valor)
