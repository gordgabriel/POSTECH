from cadastros.models import Cliente, Veiculo
from oficina.atendimento.portas.repositorios import CadastroRepositorio
from oficina.cadastros.dominio.placa import normalizar_placa


class CadastroRepositorioDjango(CadastroRepositorio):
    def cliente_por_documento(self, cpf_cnpj):
        return Cliente.objects.por_documento(cpf_cnpj).values_list('id', flat=True).first()

    def criar_cliente(self, dados):
        return Cliente.objects.create(**dados).pk

    def veiculo_por_placa(self, placa):
        return (
            Veiculo.objects.filter(placa=normalizar_placa(placa))
            .values_list('id', 'cliente_id')
            .first()
        )

    def criar_veiculo(self, dados, cliente_id):
        return Veiculo.objects.create(cliente_id=cliente_id, **dados).pk
