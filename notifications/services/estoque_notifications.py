from django.conf import settings

from notifications.services.email_service import send_notification_email


def _destino_operacao():
    return getattr(settings, 'EMAIL_OPERACAO', '') or settings.DEFAULT_FROM_EMAIL


def alertar_estoque_minimo(pecas) -> int:
    """Política: estoque abaixo do mínimo, então alertar reposição."""
    abaixo = [p for p in pecas if p.abaixo_do_minimo]
    if not abaixo:
        return 0

    return send_notification_email(
        to=_destino_operacao(),
        template_key='estoque_minimo',
        context={
            'pecas': [
                {
                    'nome': p.nome,
                    'disponivel': p.quantidade_disponivel,
                    'minimo': p.estoque_minimo,
                    'reservada': p.quantidade_reservada,
                }
                for p in abaixo
            ],
        },
    )


def alertar_estoque_insuficiente(ordem_servico, faltantes) -> int:
    """Política: estoque insuficiente, então notificar atendente e pausar a OS."""
    return send_notification_email(
        to=_destino_operacao(),
        template_key='estoque_insuficiente',
        context={
            'os_ref': str(ordem_servico.uuid)[:8].upper(),
            'os_uuid': str(ordem_servico.uuid),
            'cliente_nome': ordem_servico.cliente.nome,
            'veiculo_placa': ordem_servico.veiculo.placa,
            'status_display': ordem_servico.get_status_display(),
            'faltantes': [
                {
                    'nome': f['peca'].nome,
                    'solicitado': f['solicitado'],
                    'disponivel': f['disponivel'],
                }
                for f in faltantes
            ],
        },
    )
