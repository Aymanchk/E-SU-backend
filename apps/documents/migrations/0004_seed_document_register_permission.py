from django.db import migrations


PERMISSION_CODE = "documents.register"


def seed_register_permission(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Role = apps.get_model("accounts", "Role")
    RolePermission = apps.get_model("accounts", "RolePermission")

    permission, _ = Permission.objects.update_or_create(
        code=PERMISSION_CODE,
        defaults={
            "name": "Регистрация документов",
            "group": "documents",
            "description": "Присвоение неизменяемого регистрационного номера",
        },
    )
    for role in Role.objects.filter(code__in=["admin", "office"]):
        RolePermission.objects.get_or_create(role=role, permission=permission)


def unseed_register_permission(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Permission.objects.filter(code=PERMISSION_CODE).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0003_documentnumbercounter_and_more"),
        ("accounts", "0003_seed_permissions_and_roles"),
    ]

    operations = [
        migrations.RunPython(seed_register_permission, unseed_register_permission),
    ]
