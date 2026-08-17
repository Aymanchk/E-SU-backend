"""Проверка прав доступа."""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class HasPermission(BasePermission):
    """
    Проверяет одно право, указанное во вьюхе:

        class AuditViewSet(...):
            permission_classes = [IsAuthenticated, HasPermission]
            required_permission = "audit.view"
    """

    message = "Недостаточно прав для выполнения действия"

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        required = getattr(view, "required_permission", None)
        if not required:
            return True

        return user.has_permission(required)


class HasPermissionPerAction(BasePermission):
    """
    Разные права на разные действия ViewSet:

        class UserViewSet(...):
            permission_classes = [IsAuthenticated, HasPermissionPerAction]
            permission_map = {
                "list": "users.manage",
                "create": "users.manage",
                "retrieve": None,      # None означает "любому авторизованному"
            }

    Если действия нет в словаре, доступ запрещён (deny by default).
    """

    message = "Недостаточно прав для выполнения действия"

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        permission_map = getattr(view, "permission_map", {})
        action = getattr(view, "action", None)

        # Let DRF return 405 for an HTTP method that is not mapped to any action.
        if action is None:
            return True
        if action not in permission_map:
            return False

        required = permission_map[action]
        if required is None:
            return True

        if isinstance(required, list | tuple):
            return any(user.has_permission(code) for code in required)

        return user.has_permission(required)


class IsAdminRole(BasePermission):
    """Только суперпользователь или роль admin."""

    message = "Действие доступно только администраторам"

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return bool(user.role_id and user.role.code == "admin")


class IsSelfOrHasPermission(BasePermission):
    """
    Пользователь может работать со своим объектом,
    либо ему нужно право из required_permission.
    """

    message = "Недостаточно прав для выполнения действия"

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if obj == user or getattr(obj, "user_id", None) == user.id:
            return True

        required = getattr(view, "required_permission", None)
        if not required:
            return request.method in SAFE_METHODS

        return user.has_permission(required)
