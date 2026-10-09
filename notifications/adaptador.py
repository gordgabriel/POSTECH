from notifications.services.estoque_notifications import (
    alertar_estoque_insuficiente,
    alertar_estoque_minimo,
)
from notifications.services.os_notifications import (
    notificar_os_encerrada,
    notificar_status_os,
)
from oficina.atendimento.portas.notificador import Notificador
from oficina.estoque.portas.repositorios import AlertaDeEstoque


class NotificadorEmail(Notificador):
    def __init__(self, ordem_servico):
        self.ordem_servico = ordem_servico

    def status_alterado(self, os_id, status_anterior):
        return notificar_status_os(self.ordem_servico(os_id), status_anterior)

    def os_encerrada(self, os_id):
        return notificar_os_encerrada(self.ordem_servico(os_id))

    def estoque_insuficiente(self, os_id, faltantes):
        return alertar_estoque_insuficiente(self.ordem_servico(os_id), faltantes)


class AlertaDeEstoqueEmail(AlertaDeEstoque):
    def estoque_minimo(self, pecas):
        return alertar_estoque_minimo(pecas)
