"""Удаление старых записей журнала аудита."""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.audit.models import AuditLog


class Command(BaseCommand):
    help = "Удаляет записи журнала аудита старше указанного количества дней"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=365,
            help="Хранить записи за последние N дней (по умолчанию 365)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать количество, ничего не удалять",
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options["days"])
        queryset = AuditLog.objects.filter(created_at__lt=cutoff)
        count = queryset.count()

        if options["dry_run"]:
            self.stdout.write(f"Будет удалено записей: {count}")
            return

        # Удаление через QuerySet минует метод delete() модели
        queryset.delete()
        self.stdout.write(self.style.SUCCESS(f"Удалено записей: {count}"))
