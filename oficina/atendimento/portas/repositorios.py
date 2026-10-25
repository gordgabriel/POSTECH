from abc import ABC, abstractmethod


class OrdemServicoRepositorio(ABC):
    @abstractmethod
    def criar(self, dados): ...

    @abstractmethod
    def obter(self, os_id): ...

    @abstractmethod
    def salvar(self, ordem_servico, campos=None): ...

    @abstractmethod
    def itens_peca_reservados(self, os_id): ...

    @abstractmethod
    def possui_orcamento_aprovado(self, os_id): ...


class OrcamentoRepositorio(ABC):
    @abstractmethod
    def obter(self, orcamento_id): ...

    @abstractmethod
    def em_aberto(self, os_id): ...

    @abstractmethod
    def ha_itens_pendentes(self, os_id): ...

    @abstractmethod
    def ultima_sequencia(self, os_id): ...

    @abstractmethod
    def criar(self, os_id, sequencia): ...

    @abstractmethod
    def vincular_itens_pendentes(self, os_id, orcamento_id): ...

    @abstractmethod
    def subtotais(self, orcamento_id): ...

    @abstractmethod
    def itens_peca(self, orcamento_id): ...

    @abstractmethod
    def salvar(self, orcamento, campos): ...

    @abstractmethod
    def descartar_itens(self, orcamento_id): ...


class ItemRepositorio(ABC):
    @abstractmethod
    def preco_de_catalogo(self, item): ...

    @abstractmethod
    def quantidade_gravada(self, item_id): ...

    @abstractmethod
    def gravar(self, item): ...

    @abstractmethod
    def remover(self, item): ...

    @abstractmethod
    def incluir(self, os_id, catalogo, referencia_id, quantidade): ...


class CadastroRepositorio(ABC):
    @abstractmethod
    def cliente_por_documento(self, cpf_cnpj): ...

    @abstractmethod
    def criar_cliente(self, dados): ...

    @abstractmethod
    def veiculo_por_placa(self, placa): ...

    @abstractmethod
    def criar_veiculo(self, dados, cliente_id): ...
