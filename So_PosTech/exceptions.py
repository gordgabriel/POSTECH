from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import ProtectedError, RestrictedError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def api_exception_handler(exc, context):
    """Traduz erros do domínio em resposta da API, em vez de deixar subir como 500."""
    if isinstance(exc, DjangoValidationError):
        return Response(
            {'detail': exc.messages},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, (ProtectedError, RestrictedError)):
        objetos = getattr(exc, 'protected_objects', None) or getattr(
            exc, 'restricted_objects', [],
        )
        vinculos = ', '.join(sorted({obj._meta.verbose_name for obj in objetos}))
        return Response(
            {
                'detail': (
                    f'Registro em uso e não pode ser removido: existe '
                    f'{vinculos} vinculado a ele. '
                    'Desative o cadastro em vez de excluí-lo.'
                ),
            },
            status=status.HTTP_409_CONFLICT,
        )

    return drf_exception_handler(exc, context)
