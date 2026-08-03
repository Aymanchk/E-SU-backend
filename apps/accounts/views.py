"""API пользователей, ролей и прав."""

from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit.constants import AuditAction
from apps.audit.services import log_action
from apps.common.permissions import HasPermissionPerAction
from apps.common.utils import generate_password

from .filters import UserFilter
from .models import Permission, Role, User, UserStatus
from .serializers import (
    PermissionSerializer,
    RoleDetailSerializer,
    RoleListSerializer,
    RolePermissionsUpdateSerializer,
    RoleWriteSerializer,
    UserCreateSerializer,
    UserDetailSerializer,
    UserListSerializer,
    UserPublicSerializer,
    UserUpdateSerializer,
)
from .tasks import send_account_blocked_email, send_account_created_email


@extend_schema_view(
    list=extend_schema(summary="Список ролей", tags=["Roles"]),
    retrieve=extend_schema(summary="Роль", tags=["Roles"]),
    create=extend_schema(summary="Создать роль", tags=["Roles"]),
    partial_update=extend_schema(summary="Изменить роль", tags=["Roles"]),
    destroy=extend_schema(summary="Удалить роль", tags=["Roles"]),
)
class RoleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasPermissionPerAction]
    permission_map = {
        "list": None,
        "retrieve": None,
        "create": "users.manage",
        "update": "users.manage",
        "partial_update": "users.manage",
        "destroy": "users.manage",
        "set_permissions": "users.manage",
    }
    search_fields = ["name", "code"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return Role.objects.prefetch_related("permissions").annotate(
            users_count=Count("users", filter=Q(users__is_deleted=False))
        )

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return RoleWriteSerializer
        if self.action == "retrieve":
            return RoleDetailSerializer
        return RoleListSerializer

    def perform_create(self, serializer):
        role = serializer.save()
        log_action(
            self.request,
            action=AuditAction.ROLE_CREATE,
            obj=role,
            description=f"Создана роль {role.name}",
        )

    def perform_update(self, serializer):
        role = serializer.save()
        log_action(
            self.request,
            action=AuditAction.ROLE_UPDATE,
            obj=role,
            description=f"Изменена роль {role.name}",
        )

    def perform_destroy(self, instance):
        if instance.is_system:
            raise serializers.ValidationError("Системную роль удалить нельзя")
        if instance.users.filter(is_deleted=False).exists():
            raise serializers.ValidationError(
                "Роль назначена пользователям, сначала переназначьте их"
            )
        log_action(
            self.request,
            action=AuditAction.ROLE_DELETE,
            obj=instance,
            description=f"Удалена роль {instance.name}",
        )
        instance.delete()

    @extend_schema(
        summary="Заменить набор прав роли",
        tags=["Roles"],
        request=RolePermissionsUpdateSerializer,
        responses={200: RoleDetailSerializer},
    )
    @action(detail=True, methods=["put"], url_path="permissions")
    def set_permissions(self, request, pk=None):
        role = self.get_object()
        serializer = RolePermissionsUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        codes = serializer.validated_data["permissions"]
        old_codes = set(role.permission_codes)
        role.permissions.set(Permission.objects.filter(code__in=codes))
        new_codes = set(codes)

        log_action(
            request,
            action=AuditAction.ROLE_PERMISSIONS_UPDATE,
            obj=role,
            description=f"Изменены права роли {role.name}",
            metadata={
                "added": sorted(new_codes - old_codes),
                "removed": sorted(old_codes - new_codes),
            },
        )

        role = self.get_queryset().get(pk=role.pk)
        return Response(RoleDetailSerializer(role).data)


@extend_schema(summary="Список всех прав", tags=["Roles"])
class PermissionListView(ListAPIView):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    filterset_fields = ["group"]
    search_fields = ["code", "name"]


@extend_schema_view(
    list=extend_schema(summary="Список пользователей", tags=["Users"]),
    retrieve=extend_schema(summary="Пользователь", tags=["Users"]),
    create=extend_schema(summary="Создать пользователя", tags=["Users"]),
    partial_update=extend_schema(summary="Изменить пользователя", tags=["Users"]),
    destroy=extend_schema(summary="Удалить пользователя", tags=["Users"]),
)
class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasPermissionPerAction]
    permission_map = {
        "list": None,  # видимость ограничивается в get_queryset
        "retrieve": None,
        "create": "users.manage",
        "update": "users.manage",
        "partial_update": "users.manage",
        "destroy": "users.manage",
        "activate": "users.manage",
        "block": "users.manage",
        "reset_password": "users.manage",
    }
    filterset_class = UserFilter
    search_fields = ["email", "first_name", "last_name", "middle_name", "position"]
    ordering_fields = ["last_name", "email", "created_at", "status"]
    ordering = ["last_name", "first_name"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        """
        Видимость по ТЗ:
        - администратор видит всех
        - руководитель видит пользователей своего подразделения
        - сотрудник видит ограниченные публичные данные коллег
        """
        user = self.request.user
        queryset = User.objects.select_related("department", "role", "manager")

        if not user.is_authenticated:
            return queryset.none()

        if user.is_superuser or user.has_permission("users.manage"):
            return queryset

        if user.role_id and user.role.code == "manager" and user.department_id:
            department_ids = [user.department_id]
            department_ids += [d.id for d in user.department.get_descendants()]
            return queryset.filter(department_id__in=department_ids)

        return queryset.filter(status=UserStatus.ACTIVE)

    def get_serializer_class(self):
        if getattr(self, "swagger_fake_view", False):
            return UserDetailSerializer

        user = self.request.user
        full_access = user.is_authenticated and (
            user.is_superuser or user.has_permission("users.manage")
        )

        if self.action == "create":
            return UserCreateSerializer
        if self.action in ("update", "partial_update"):
            return UserUpdateSerializer
        if self.action == "list":
            return UserListSerializer if full_access else UserPublicSerializer
        if self.action == "retrieve":
            if full_access or self.get_object() == user:
                return UserDetailSerializer
            if user.role_id and user.role.code == "manager":
                return UserListSerializer
            return UserPublicSerializer
        return UserDetailSerializer

    # -- создание -----------------------------------------------------------

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        if request.data.get("send_credentials", True):
            send_account_created_email.delay(user.email, user.full_name, user._generated_password)

        log_action(
            request,
            action=AuditAction.USER_CREATE,
            obj=user,
            description=f"Создан пользователь {user.email}",
            metadata={
                "role": user.role.code if user.role_id else None,
                "department": user.department.code if user.department_id else None,
            },
        )

        return Response(UserDetailSerializer(user).data, status=status.HTTP_201_CREATED)

    # -- изменение ------------------------------------------------------------

    def perform_update(self, serializer):
        before = {
            "role": serializer.instance.role_id,
            "department": serializer.instance.department_id,
            "status": serializer.instance.status,
        }
        user = serializer.save()
        after = {
            "role": user.role_id,
            "department": user.department_id,
            "status": user.status,
        }
        changes = {k: [str(before[k]), str(after[k])] for k in before if before[k] != after[k]}

        log_action(
            self.request,
            action=AuditAction.USER_UPDATE,
            obj=user,
            description=f"Изменён пользователь {user.email}",
            metadata={"changes": changes, "fields": list(self.request.data.keys())},
        )

        if "role" in changes:
            log_action(
                self.request,
                action=AuditAction.USER_ROLE_CHANGE,
                obj=user,
                description=f"Изменена роль пользователя {user.email}",
                metadata={"change": changes["role"]},
            )

    # -- удаление ------------------------------------------------------------

    def perform_destroy(self, instance):
        """
        ТЗ: удаление мягкое. Физически удалять нельзя,
        если есть документы или записи в журнале.
        """
        if instance == self.request.user:
            raise serializers.ValidationError("Нельзя удалить собственную учётную запись")

        if instance.is_superuser and not self.request.user.is_superuser:
            raise serializers.ValidationError("Недостаточно прав")

        log_action(
            self.request,
            action=AuditAction.USER_DELETE,
            obj=instance,
            description=f"Удалён пользователь {instance.email}",
        )
        instance.delete()  # мягкое удаление, см. модель

    # -- действия ------------------------------------------------------------

    @extend_schema(
        summary="Активировать пользователя",
        tags=["Users"],
        request=None,
        responses={200: UserDetailSerializer},
    )
    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        user = self.get_object()
        user.activate()
        log_action(
            request,
            action=AuditAction.USER_ACTIVATE,
            obj=user,
            description=f"Активирован пользователь {user.email}",
        )
        return Response(UserDetailSerializer(user).data)

    @extend_schema(
        summary="Заблокировать пользователя",
        tags=["Users"],
        request=None,
        responses={200: UserDetailSerializer},
    )
    @action(detail=True, methods=["post"])
    def block(self, request, pk=None):
        user = self.get_object()

        if user == request.user:
            raise serializers.ValidationError("Нельзя заблокировать самого себя")
        if user.is_superuser:
            raise serializers.ValidationError("Нельзя заблокировать суперпользователя")

        user.block()
        send_account_blocked_email.delay(user.email, user.full_name)

        log_action(
            request,
            action=AuditAction.USER_BLOCK,
            obj=user,
            description=f"Заблокирован пользователь {user.email}",
        )
        return Response(UserDetailSerializer(user).data)

    @extend_schema(
        summary="Сбросить пароль пользователя", tags=["Users"], request=None, responses={200: dict}
    )
    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        user = self.get_object()

        password = generate_password()
        user.set_password(password)
        user.save(update_fields=["password"])

        send_account_created_email.delay(user.email, user.full_name, password)

        log_action(
            request,
            action=AuditAction.USER_RESET_PASSWORD,
            obj=user,
            description=f"Сброшен пароль пользователя {user.email}",
        )

        return Response({"message": "Новый пароль отправлен пользователю на email"})
