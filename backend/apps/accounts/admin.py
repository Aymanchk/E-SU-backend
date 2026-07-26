from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import Permission, Role, RolePermission, User


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name")


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User

    list_display = (
        "email",
        "last_name",
        "first_name",
        "role",
        "department",
        "status",
        "is_active",
    )
    list_filter = ("status", "is_active", "is_staff", "role", "department")
    search_fields = ("email", "first_name", "last_name", "middle_name", "position")
    ordering = ("last_name", "first_name")
    readonly_fields = ("created_at", "updated_at", "last_login", "deleted_at")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("ФИО", {"fields": ("last_name", "first_name", "middle_name")}),
        ("Контакты", {"fields": ("phone", "position")}),
        ("Организация", {"fields": ("department", "manager", "role")}),
        ("Статус", {"fields": ("status", "is_active", "is_staff", "is_superuser")}),
        ("Удаление", {"fields": ("is_deleted", "deleted_at")}),
        ("Даты", {"fields": ("last_login", "created_at", "updated_at")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "password1",
                    "password2",
                    "role",
                    "department",
                ),
            },
        ),
    )

    def get_queryset(self, request):
        # В админке показываем в том числе удалённых
        return User.all_objects.all()


class RolePermissionInline(admin.TabularInline):
    model = RolePermission
    extra = 1
    autocomplete_fields = ["permission"]


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_system", "users_count")
    list_filter = ("is_system",)
    search_fields = ("name", "code")
    inlines = [RolePermissionInline]

    @admin.display(description="Пользователей")
    def users_count(self, obj):
        return obj.users.count()


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "group")
    list_filter = ("group",)
    search_fields = ("code", "name")
