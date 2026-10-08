from abc import ABC, abstractmethod


class Notificador(ABC):
    """Avisos ao cliente e à oficina."""

    @abstractmethod
    def status_alterado(self, os_id, status_anterior): ...

    @abstractmethod
    def os_encerrada(self, os_id): ...

    @abstractmethod
    def estoque_insuficiente(self, os_id, faltantes): ...
