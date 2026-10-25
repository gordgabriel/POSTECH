from oficina.atendimento.dominio.ordem_servico import (
    exigir_dados_para_cadastro,
    exigir_veiculo_do_cliente,
)


class AbrirOS:
    def __init__(self, cadastros, ordens, itens, unidade):
        self.cadastros = cadastros
        self.ordens = ordens
        self.itens = itens
        self.unidade = unidade

    def executar(self, cliente, veiculo, descricao, observacoes=None, servicos=(), pecas=()):
        with self.unidade.atomico():
            cliente_id = self._cliente(cliente)
            veiculo_id = self._veiculo(veiculo, cliente_id)
            ordem_servico = self.ordens.criar({
                'descricao': descricao,
                'observacoes': observacoes,
                'cliente_id': cliente_id,
                'veiculo_id': veiculo_id,
            })
            for catalogo, itens in (('servico', servicos), ('peca', pecas)):
                for referencia_id, quantidade in itens:
                    self.itens.incluir(ordem_servico.id, catalogo, referencia_id, quantidade)
            return ordem_servico

    def _cliente(self, dados):
        cliente_id = self.cadastros.cliente_por_documento(dados['cpf_cnpj'])
        if cliente_id is not None:
            return cliente_id
        exigir_dados_para_cadastro(
            dados, ('nome', 'email'), 'cliente', 'Cliente não encontrado pelo CPF/CNPJ',
        )
        return self.cadastros.criar_cliente(dados)

    def _veiculo(self, dados, cliente_id):
        encontrado = self.cadastros.veiculo_por_placa(dados['placa'])
        if encontrado is not None:
            veiculo_id, dono_id = encontrado
            exigir_veiculo_do_cliente(dono_id, cliente_id)
            return veiculo_id
        exigir_dados_para_cadastro(
            dados, ('marca', 'modelo', 'ano'), 'veiculo', 'Veículo não encontrado pela placa',
        )
        return self.cadastros.criar_veiculo(dados, cliente_id)
