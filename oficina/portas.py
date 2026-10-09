from abc import ABC, abstractmethod


class UnidadeDeTrabalho(ABC):
    @abstractmethod
    def atomico(self): ...

    @abstractmethod
    def ao_confirmar(self, funcao): ...


class Relogio(ABC):
    @abstractmethod
    def agora(self): ...
