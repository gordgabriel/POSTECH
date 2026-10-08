from abc import ABC, abstractmethod


class PecaRepositorio(ABC):
    @abstractmethod
    def travar(self, peca_id): ...

    @abstractmethod
    def travar_varias(self, pecas_ids): ...

    @abstractmethod
    def obter_varias(self, pecas_ids): ...

    @abstractmethod
    def salvar(self, peca, campos): ...


class AlertaDeEstoque(ABC):
    @abstractmethod
    def estoque_minimo(self, pecas): ...
