"""Начальное заполнение прав и ролей."""

from django.db import migrations

PERMISSIONS = [
    # (code, name, group)
    ("documents.view", "Просмотр документов", "documents"),
    ("documents.create", "Создание документов", "documents"),
    ("documents.edit", "Редактирование документов", "documents"),
    ("documents.approve", "Согласование документов", "documents"),
    ("documents.return", "Возврат документов на доработку", "documents"),
    ("documents.archive", "Архивирование документов", "documents"),
    ("users.manage", "Управление пользователями", "users"),
    ("departments.manage", "Управление подразделениями", "departments"),
    ("categories.manage", "Управление категориями", "categories"),
    ("audit.view", "Просмотр журнала аудита", "audit"),
    ("settings.manage", "Управление системными настройками", "settings"),
]

ROLES = {
    "admin": {
        "name": "Администратор",
        "description": "Полный доступ ко всем функциям системы",
        "permissions": [code for code, _, _ in PERMISSIONS],
    },
    "manager": {
        "name": "Руководитель",
        "description": "Согласование документов, просмотр сотрудников подразделения",
        "permissions": [
            "documents.view",
            "documents.create",
            "documents.edit",
            "documents.approve",
            "documents.return",
        ],
    },
    "office": {
        "name": "Канцелярия",
        "description": "Регистрация, архивирование документов, справочники",
        "permissions": [
            "documents.view",
            "documents.create",
            "documents.edit",
            "documents.archive",
            "categories.manage",
        ],
    },
    "employee": {
        "name": "Сотрудник",
        "description": "Создание и просмотр своих документов",
        "permissions": [
            "documents.view",
            "documents.create",
        ],
    },
}


def seed(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Role = apps.get_model("accounts", "Role")
    RolePermission = apps.get_model("accounts", "RolePermission")

    permissions = {}
    for code, name, group in PERMISSIONS:
        obj, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "group": group},
        )
        permissions[code] = obj

    for code, data in ROLES.items():
        role, _ = Role.objects.update_or_create(
            code=code,
            defaults={
                "name": data["name"],
                "description": data["description"],
                "is_system": True,
            },
        )
        for permission_code in data["permissions"]:
            RolePermission.objects.get_or_create(
                role=role,
                permission=permissions[permission_code],
            )


def unseed(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    Role.objects.filter(is_system=True).delete()
    Permission.objects.filter(
        code__in=[code for code, _, _ in PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
