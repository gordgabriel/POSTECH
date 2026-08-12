from notifications.services.email_service import send_notification_email
from so.models import StatusOS


STATUS_TEMPLATE_MAP = {
    StatusOS.EM_DIAGNOSTICO: 'os_em_diagnostico',
    StatusOS.AGUARDANDO_APROVACAO: 'os_aguardando_aprovacao',
    StatusOS.EM_EXECUCAO: 'os_em_execucao',
    StatusOS.FINALIZADA: 'os_finalizada',
    StatusOS.ENTREGUE: 'os_entregue',
    StatusOS.CANCELADA: 'os_cancelada',
}


def _build_os_context(ordem_servico, status_anterior: str | None) -> dict:
    veiculo = ordem_servico.veiculo
    return {
        'cliente_nome': ordem_servico.cliente.nome,
        'os_uuid': str(ordem_servico.uuid),
        'os_ref': str(ordem_servico.uuid)[:8].upper(),
        'veiculo_placa': veiculo.placa,
        'veiculo_marca': veiculo.marca,
        'veiculo_modelo': veiculo.modelo,
        'veiculo_ano': veiculo.ano,
        'status_display': ordem_servico.get_status_display(),
        'descricao': ordem_servico.descricao,
        'diagnostico': ordem_servico.diagnostico or '',
        'data_abertura': ordem_servico.data_abertura,
        'status_anterior': status_anterior,
    }


def notificar_status_os(ordem_servico, status_anterior: str | None) -> int:
    """Envia e-mail ao cliente quando o status da OS muda."""
    template_key = STATUS_TEMPLATE_MAP.get(ordem_servico.status)
    if not template_key:
        return 0

    email = ordem_servico.cliente.email
    if not email:
        return 0

    context = _build_os_context(ordem_servico, status_anterior)
    return send_notification_email(
        to=email,
        template_key=template_key,
        context=context,
    )
