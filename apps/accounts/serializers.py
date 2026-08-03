"""Сериализаторы приложения accounts."""

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.organizations.models import Department
from apps.organizations.serializers import DepartmentShortSerializer

from .models import Permission, Role, User, UserStatus

# ---------------------------------------------------------------------------
# Вспомогательные короткие сериализаторы
# ---------------------------------------------------------------------------


class RoleShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "code", "name"]


class UserShortSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "position"]


# ---------------------------------------------------------------------------
# Вход
# ---------------------------------------------------------------------------


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    default_error_messages = {
        "invalid_credentials": "Неверный email или пароль",
        "blocked": "Учётная запись заблокирована. Обратитесь к администратору",
        "dismissed": "Учётная запись отключена",
        "inactive": "Учётная запись неактивна",
    }

    def validate(self, attrs):
        email = attrs["email"].lower().strip()
        password = attrs["password"]

        # Берём пользователя заранее, чтобы отличить блокировку от неверного пароля
        user = User.all_objects.filter(email=email).first()

        if user is None or not user.check_password(password):
            self.fail("invalid_credentials")

        if user.is_deleted:
            self.fail("invalid_credentials")

        if user.status == UserStatus.BLOCKED:
            self.fail("blocked")

        if user.status == UserStatus.DISMISSED:
            self.fail("dismissed")

        if not user.is_active:
            self.fail("inactive")

        # Финальная проверка через стандартный механизм Django
        authenticated = authenticate(
            request=self.context.get("request"),
            username=email,
            password=password,
        )
        if authenticated is None:
            self.fail("invalid_credentials")

        attrs["user"] = authenticated
        return attrs


class TokenPairSerializer(serializers.Serializer):
    """Только для описания схемы в Swagger."""

    access = serializers.CharField()
    refresh = serializers.CharField()


# ---------------------------------------------------------------------------
# Профиль
# ---------------------------------------------------------------------------


class MeSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    short_name = serializers.CharField(read_only=True)
    role = RoleShortSerializer(read_only=True)
    department = DepartmentShortSerializer(read_only=True)
    manager = UserShortSerializer(read_only=True)
    permissions = serializers.SerializerMethodField()
    available_actions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "middle_name",
            "full_name",
            "short_name",
            "phone",
            "position",
            "department",
            "manager",
            "role",
            "status",
            "is_active",
            "is_staff",
            "is_superuser",
            "last_login",
            "created_at",
            "updated_at",
            "permissions",
            "available_actions",
        ]
        read_only_fields = [
            "id",
            "email",
            "position",
            "department",
            "manager",
            "role",
            "status",
            "is_active",
            "is_staff",
            "is_superuser",
            "last_login",
            "created_at",
            "updated_at",
        ]

    def get_permissions(self, obj) -> list:
        return sorted(obj.get_permission_codes())

    def get_available_actions(self, obj) -> dict:
        """Флаги для интерфейса, чтобы фронт не парсил коды прав руками."""
        codes = obj.get_permission_codes()
        return {
            "can_manage_users": "users.manage" in codes or obj.is_superuser,
            "can_manage_departments": "departments.manage" in codes or obj.is_superuser,
            "can_manage_categories": "categories.manage" in codes or obj.is_superuser,
            "can_manage_settings": "settings.manage" in codes or obj.is_superuser,
            "can_view_audit": "audit.view" in codes or obj.is_superuser,
            "can_create_documents": "documents.create" in codes or obj.is_superuser,
            "can_approve_documents": "documents.approve" in codes or obj.is_superuser,
            "can_archive_documents": "documents.archive" in codes or obj.is_superuser,
        }

    def validate_phone(self, value):
        from apps.common.utils import normalize_phone

        return normalize_phone(value)


# ---------------------------------------------------------------------------
# Пароли
# ---------------------------------------------------------------------------


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Текущий пароль указан неверно")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "Пароли не совпадают"})
        if attrs["old_password"] == attrs["new_password"]:
            raise serializers.ValidationError(
                {"new_password": "Новый пароль должен отличаться от текущего"}
            )

        user = self.context["request"].user
        try:
            validate_password(attrs["new_password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)}) from exc

        return attrs


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "Пароли не совпадают"})
        return attrs


# ---------------------------------------------------------------------------
# Права и роли
# ---------------------------------------------------------------------------


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "code", "name", "group", "description"]


class RoleListSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()
    users_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Role
        fields = [
            "id",
            "code",
            "name",
            "description",
            "is_system",
            "permissions",
            "users_count",
            "created_at",
            "updated_at",
        ]

    def get_permissions(self, obj) -> list:
        return [p.code for p in obj.permissions.all()]


class RoleDetailSerializer(RoleListSerializer):
    permissions_detail = PermissionSerializer(source="permissions", many=True, read_only=True)

    class Meta(RoleListSerializer.Meta):
        fields = RoleListSerializer.Meta.fields + ["permissions_detail"]


class RoleWriteSerializer(serializers.ModelSerializer):
    permissions = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )

    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "permissions"]

    def validate_permissions(self, value):
        existing = set(Permission.objects.filter(code__in=value).values_list("code", flat=True))
        unknown = set(value) - existing
        if unknown:
            raise serializers.ValidationError(f"Неизвестные права: {', '.join(sorted(unknown))}")
        return value

    def create(self, validated_data):
        codes = validated_data.pop("permissions", [])
        role = Role.objects.create(**validated_data)
        if codes:
            role.permissions.set(Permission.objects.filter(code__in=codes))
        return role

    def update(self, instance, validated_data):
        codes = validated_data.pop("permissions", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if codes is not None:
            instance.permissions.set(Permission.objects.filter(code__in=codes))
        return instance


class RolePermissionsUpdateSerializer(serializers.Serializer):
    """Для PUT /api/roles/{id}/permissions/"""

    permissions = serializers.ListField(child=serializers.CharField())

    def validate_permissions(self, value):
        existing = set(Permission.objects.filter(code__in=value).values_list("code", flat=True))
        unknown = set(value) - existing
        if unknown:
            raise serializers.ValidationError(f"Неизвестные права: {', '.join(sorted(unknown))}")
        return value


# ---------------------------------------------------------------------------
# Пользователи
# ---------------------------------------------------------------------------


class UserListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    role = RoleShortSerializer(read_only=True)
    department = DepartmentShortSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "middle_name",
            "full_name",
            "phone",
            "position",
            "department",
            "role",
            "status",
            "is_active",
            "created_at",
        ]


class UserPublicSerializer(serializers.ModelSerializer):
    """Ограниченный набор данных, который видит обычный сотрудник."""

    full_name = serializers.CharField(read_only=True)
    department = DepartmentShortSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "position", "department"]


class UserDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    role = RoleShortSerializer(read_only=True)
    department = DepartmentShortSerializer(read_only=True)
    manager = UserShortSerializer(read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "middle_name",
            "full_name",
            "phone",
            "position",
            "department",
            "manager",
            "role",
            "status",
            "is_active",
            "is_staff",
            "is_superuser",
            "last_login",
            "created_at",
            "updated_at",
            "permissions",
        ]

    def get_permissions(self, obj) -> list:
        return sorted(obj.get_permission_codes())


class UserCreateSerializer(serializers.ModelSerializer):
    role = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(), required=False, allow_null=True
    )
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), required=False, allow_null=True
    )
    manager = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )
    send_credentials = serializers.BooleanField(
        default=True,
        write_only=True,
        help_text="Отправить пользователю письмо с доступами",
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "middle_name",
            "phone",
            "position",
            "department",
            "manager",
            "role",
            "status",
            "send_credentials",
        ]

    def validate_email(self, value):
        value = value.lower().strip()
        if User.all_objects.filter(email=value).exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует")
        return value

    def create(self, validated_data):
        from apps.common.utils import generate_password

        validated_data.pop("send_credentials", None)
        password = generate_password()
        validated_data.setdefault("status", UserStatus.INVITED)
        user = User.objects.create_user(password=password, **validated_data)
        # пароль нужен выше для отправки письма, но не для ответа API
        user._generated_password = password
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    role = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(), required=False, allow_null=True
    )
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), required=False, allow_null=True
    )
    manager = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "middle_name",
            "phone",
            "position",
            "department",
            "manager",
            "role",
            "status",
        ]

    def validate_manager(self, value):
        if self.instance and value and value.pk == self.instance.pk:
            raise serializers.ValidationError("Пользователь не может быть своим руководителем")
        return value

    def validate_status(self, value):
        request = self.context.get("request")
        if request and not request.user.has_permission("users.manage"):
            raise serializers.ValidationError("Недостаточно прав для смены статуса")
        return value
