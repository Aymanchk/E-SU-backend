"""Создать демонстрационные данные для ручной проверки API."""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Role, User, UserStatus
from apps.organizations.models import Department


class Command(BaseCommand):
    help = "Создать демо-подразделения и пользователей"

    @transaction.atomic
    def handle(self, *args, **options):
        rector, _ = Department.objects.get_or_create(
            code="rectorate", defaults={"name": "Ректорат"}
        )
        it, _ = Department.objects.get_or_create(
            code="it", defaults={"name": "IT отдел", "parent": rector}
        )
        buh, _ = Department.objects.get_or_create(
            code="accounting", defaults={"name": "Бухгалтерия", "parent": rector}
        )

        roles = {r.code: r for r in Role.objects.all()}

        demo_users = [
            ("admin@esu.kg", "Админов", "Админ", "admin", rector),
            ("manager@esu.kg", "Руководителев", "Пётр", "manager", it),
            ("office@esu.kg", "Канцелярова", "Анна", "office", rector),
            ("employee@esu.kg", "Сотрудников", "Иван", "employee", it),
            ("buh@esu.kg", "Бухгалтерова", "Мария", "employee", buh),
        ]

        for email, last_name, first_name, role_code, department in demo_users:
            if User.all_objects.filter(email=email).exists():
                continue
            user = User.objects.create_user(
                email=email,
                password="DemoPass123!",
                first_name=first_name,
                last_name=last_name,
                role=roles.get(role_code),
                department=department,
                status=UserStatus.ACTIVE,
                position="Демо",
            )
            self.stdout.write(self.style.SUCCESS(f"Создан {user.email}"))

        it.manager = User.objects.filter(email="manager@esu.kg").first()
        it.save(update_fields=["manager"])

        self.stdout.write(self.style.SUCCESS("Демо-данные готовы. Пароль: DemoPass123!"))
