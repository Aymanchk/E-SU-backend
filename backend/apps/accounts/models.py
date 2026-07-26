"""Пользователи, роли и права доступа."""

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone

from apps.common.models import SoftDeleteQuerySet, UUIDModel

# ---------------------------------------------------------------------------
# Права
# ---------------------------------------------------------------------------


class Permission(models.Model):
    """
    Право доступа. Код вида "documents.approve".
    Это НЕ django.contrib.auth.Permission, а наша собственная таблица,
    завязанная на бизнес-логику документооборота.
    """

    code = models.CharField("Код", max_length=100, unique=True, db_index=True)
    name = models.CharField("Название", max_length=200)
    group = models.CharField(
        "Группа",
        max_length=50,
        blank=True,
        db_index=True,
        help_text="Для группировки в интерфейсе: documents, users, settings",
    )
    description = models.TextField("Описание", blank=True)

    class Meta:
        verbose_name = "Право"
        verbose_name_plural = "Права"
        ordering = ["group", "code"]

    def __str__(self):
        return self.code


# ---------------------------------------------------------------------------
# Роли
# ---------------------------------------------------------------------------


class Role(UUIDModel):
    """Роль пользователя с набором прав."""

    code = models.SlugField("Код", max_length=50, unique=True, db_index=True)
    name = models.CharField("Название", max_length=150)
    description = models.TextField("Описание", blank=True)
    is_system = models.BooleanField(
        "Системная роль",
        default=False,
        help_text="Системные роли нельзя удалять",
    )
    permissions = models.ManyToManyField(
        Permission,
        through="RolePermission",
        related_name="roles",
        verbose_name="Права",
        blank=True,
    )
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Изменена", auto_now=True)

    class Meta:
        verbose_name = "Роль"
        verbose_name_plural = "Роли"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def permission_codes(self):
        return list(self.permissions.values_list("code", flat=True))


class RolePermission(models.Model):
    """Связь роли и права."""

    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE, related_name="role_permissions"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Право роли"
        verbose_name_plural = "Права ролей"
        constraints = [
            models.UniqueConstraint(fields=["role", "permission"], name="unique_role_permission")
        ]

    def __str__(self):
        return f"{self.role.code}:{self.permission.code}"


# ---------------------------------------------------------------------------
# Пользователь
# ---------------------------------------------------------------------------


class UserStatus(models.TextChoices):
    ACTIVE = "active", "Активен"
    BLOCKED = "blocked", "Заблокирован"
    INVITED = "invited", "Приглашён"
    DISMISSED = "dismissed", "Уволен"


class UserQuerySet(SoftDeleteQuerySet):
    def active(self):
        return self.filter(status=UserStatus.ACTIVE, is_active=True)

    def in_department(self, department):
        return self.filter(department=department)


class UserManager(BaseUserManager):
    """Менеджер пользователей с входом по email."""

    use_in_migrations = True

    def get_queryset(self):
        # Удалённые пользователи не попадают в обычные выборки
        return UserQuerySet(self.model, using=self._db).filter(is_deleted=False)

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Email обязателен для создания пользователя")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.full_clean(exclude=["password"], validate_unique=False)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("status", UserStatus.INVITED)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("status", UserStatus.ACTIVE)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Суперпользователь должен иметь is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Суперпользователь должен иметь is_superuser=True")

        return self._create_user(email, password, **extra_fields)


class AllUsersManager(BaseUserManager):
    """Видит всех, включая удалённых."""

    def get_queryset(self):
        return UserQuerySet(self.model, using=self._db)


class User(UUIDModel, AbstractBaseUser, PermissionsMixin):
    """Пользователь системы. Вход по email, username отсутствует."""

    email = models.EmailField("Email", unique=True, db_index=True)

    first_name = models.CharField("Имя", max_length=150)
    last_name = models.CharField("Фамилия", max_length=150)
    middle_name = models.CharField("Отчество", max_length=150, blank=True)
    phone = models.CharField("Телефон", max_length=30, blank=True)
    position = models.CharField("Должность", max_length=200, blank=True, db_index=True)

    department = models.ForeignKey(
        "organizations.Department",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="employees",
        verbose_name="Подразделение",
    )
    manager = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="subordinates",
        verbose_name="Руководитель",
    )
    role = models.ForeignKey(
        Role,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="users",
        verbose_name="Роль",
    )

    status = models.CharField(
        "Статус",
        max_length=20,
        choices=UserStatus.choices,
        default=UserStatus.INVITED,
        db_index=True,
    )
    is_active = models.BooleanField(
        "Может входить в систему",
        default=True,
        help_text="Django проверяет это поле при аутентификации",
    )
    is_staff = models.BooleanField("Доступ в админку", default=False)

    # Мягкое удаление
    is_deleted = models.BooleanField("Удалён", default=False, db_index=True)
    deleted_at = models.DateTimeField("Дата удаления", null=True, blank=True)

    created_at = models.DateTimeField("Создан", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("Изменён", auto_now=True)

    objects = UserManager()
    all_objects = AllUsersManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["status", "is_active"]),
            models.Index(fields=["department", "status"]),
        ]

    def __str__(self):
        return self.email

    # -- имена ------------------------------------------------------------

    @property
    def full_name(self):
        parts = [self.last_name, self.first_name, self.middle_name]
        return " ".join(p for p in parts if p)

    @property
    def short_name(self):
        initials = ""
        if self.first_name:
            initials += f" {self.first_name[0]}."
        if self.middle_name:
            initials += f"{self.middle_name[0]}."
        return f"{self.last_name}{initials}".strip()

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.first_name

    # -- права ------------------------------------------------------------

    def get_permission_codes(self):
        """Список кодов прав пользователя. Результат кешируется в объекте."""
        if hasattr(self, "_permission_codes_cache"):
            return self._permission_codes_cache

        if self.is_superuser:
            codes = set(Permission.objects.values_list("code", flat=True))
        elif self.role_id:
            codes = set(
                Permission.objects.filter(roles__id=self.role_id).values_list("code", flat=True)
            )
        else:
            codes = set()

        self._permission_codes_cache = codes
        return codes

    def has_permission(self, code: str) -> bool:
        if self.is_superuser:
            return True
        return code in self.get_permission_codes()

    def has_any_permission(self, *codes) -> bool:
        if self.is_superuser:
            return True
        return bool(set(codes) & self.get_permission_codes())

    @property
    def is_admin_role(self):
        return self.is_superuser or (self.role_id and self.role.code == "admin")

    @property
    def is_manager_role(self):
        return bool(self.role_id and self.role.code == "manager")

    # -- удаление ---------------------------------------------------------

    def delete(self, using=None, keep_parents=False):
        """Мягкое удаление."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.is_active = False
        self.status = UserStatus.DISMISSED
        self.save(update_fields=["is_deleted", "deleted_at", "is_active", "status"])

    def hard_delete(self, using=None, keep_parents=False):
        super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at"])

    # -- статусы ----------------------------------------------------------

    def block(self):
        self.status = UserStatus.BLOCKED
        self.is_active = False
        self.save(update_fields=["status", "is_active"])

    def activate(self):
        self.status = UserStatus.ACTIVE
        self.is_active = True
        self.save(update_fields=["status", "is_active"])
