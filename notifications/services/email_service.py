import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

DEFAULT_SUBJECTS = {
    'os_em_diagnostico': 'Sua OS entrou em diagnóstico',
    'os_aguardando_aprovacao': 'Orçamento aguardando sua aprovação',
    'os_em_execucao': 'Serviço em execução',
    'os_finalizada': 'Serviço concluído — veículo pronto para retirada',
    'os_entregue': 'Veículo entregue — ordem de serviço encerrada',
    'os_encerrada': 'Ordem de serviço encerrada',
    'estoque_minimo': 'Peças abaixo do estoque mínimo',
    'estoque_insuficiente': 'OS pausada: estoque insuficiente',
}


def send_notification_email(
    *,
    to: str | list[str],
    template_key: str,
    context: dict,
    subject: str | None = None,
) -> int:
    """Renderiza templates emails/{template_key}.html|.txt e envia via SMTP."""
    recipients = [to] if isinstance(to, str) else list(to)
    recipients = [r for r in recipients if r]
    if not recipients:
        return 0

    subject = subject or DEFAULT_SUBJECTS.get(
        template_key,
        'Atualização da sua ordem de serviço',
    )
    html_body = render_to_string(f'emails/{template_key}.html', context)
    text_body = render_to_string(f'emails/{template_key}.txt', context)

    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        )
        message.attach_alternative(html_body, 'text/html')
        return message.send()
    except Exception:
        logger.exception(
            'Falha ao enviar e-mail template=%s to=%s',
            template_key,
            recipients,
        )
        return 0
