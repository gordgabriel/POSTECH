from rest_framework.permissions import BasePermission

from accounts.models import UserModel


class _RolePermission(BasePermission):
    allowed_types: tuple[str, ...] = ()
    allow_admin_bypass: bool = True

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user.is_authenticated:
            return False
        if self.allow_admin_bypass and user.is_admin:
            return True
        return user.type in self.allowed_types


class IsAdmin(BasePermission):
    def has_permission(self, request, view) -> bool:
        user = request.user
        return user.is_authenticated and user.is_admin


class IsAtendente(_RolePermission):
    allowed_types = (UserModel.Tipo.ATENDENTE,)


class IsMecanico(_RolePermission):
    allowed_types = (UserModel.Tipo.MECANICO,)


class IsEstoquista(_RolePermission):
    allowed_types = (UserModel.Tipo.ESTOQUISTA,)


class IsOperador(BasePermission):
    def has_permission(self, request, view) -> bool:
        user = request.user
        return user.is_authenticated and user.is_operador


class IsCliente(BasePermission):
    def has_permission(self, request, view) -> bool:
        user = request.user
        return user.is_authenticated and user.is_cliente


def has_any_role(*roles: type[BasePermission]) -> type[BasePermission]:
    """Permite acesso se qualquer uma das permission classes passar."""

    class _AnyRole(BasePermission):
        def has_permission(self, request, view) -> bool:
            return any(role().has_permission(request, view) for role in roles)

    return _AnyRole


class PermissoesPorAcaoMixin:
    """Aplica o papel exigido por ação; o resto cai em permission_classes."""

    permissoes_por_acao: dict = {}

    def get_permissions(self):
        classes = self.permissoes_por_acao.get(self.action)
        if classes is None:
            return super().get_permissions()
        return [classe() for classe in classes]
