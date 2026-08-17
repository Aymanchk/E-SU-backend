from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.documents.models import Document, DocumentStatus

from .models import Notification, NotificationType


class NotificationService:
    @staticmethod
    @transaction.atomic
    def create(
        recipient,
        notification_type: str,
        title: str,
        message: str,
        document=None,
        dedupe_key=None,
        send_email=True,
    ) -> Notification:
        defaults = {
            "recipient": recipient,
            "type": notification_type,
            "title": title,
            "message": message,
            "document": document,
        }
        if dedupe_key:
            notification, created = Notification.objects.get_or_create(
                dedupe_key=dedupe_key, defaults=defaults
            )
        else:
            notification = Notification.objects.create(**defaults)
            created = True

        if created and send_email and settings.NOTIFICATION_EMAIL_ENABLED:
            from .tasks import send_notification_email

            transaction.on_commit(
                lambda notification_id=str(notification.id): send_notification_email.delay(
                    notification_id
                )
            )
        return notification

    @staticmethod
    def notify_many(recipients, **kwargs) -> list[Notification]:
        unique_recipients = {recipient.id: recipient for recipient in recipients if recipient}
        dedupe_key = kwargs.pop("dedupe_key", None)
        return [
            NotificationService.create(
                recipient=recipient,
                dedupe_key=(f"{dedupe_key}:{recipient.id}" if dedupe_key else None),
                **kwargs,
            )
            for recipient in unique_recipients.values()
        ]

    @staticmethod
    def mark_read(notification: Notification) -> Notification:
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at"])
        return notification

    @staticmethod
    def mark_all_read(user) -> int:
        return Notification.objects.filter(recipient=user, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )


class UpcomingDeadlineService:
    @classmethod
    def check(cls, now=None) -> int:
        now = now or timezone.now()
        soon_until = now + timedelta(days=settings.DEADLINE_APPROACHING_DAYS)
        upcoming = Document.objects.exclude(
            status__in=[DocumentStatus.COMPLETED, DocumentStatus.ARCHIVED]
        ).filter(
            responsible__isnull=False,
            deadline__gt=now,
            deadline__lte=soon_until,
        )
        created = 0
        for document in upcoming.select_related("responsible"):
            key = (
                f"deadline_approaching:{document.id}:{document.responsible_id}:"
                f"{document.deadline.isoformat()}"
            )
            existed = Notification.objects.filter(dedupe_key=key).exists()
            NotificationService.create(
                recipient=document.responsible,
                notification_type=NotificationType.DEADLINE_APPROACHING,
                title="Приближается дедлайн документа",
                message=f"Срок по документу «{document.title}» скоро истекает.",
                document=document,
                dedupe_key=key,
            )
            created += int(not existed)
        return created


class OverdueDocumentService:
    OVERDUE_STATUSES = {
        DocumentStatus.DRAFT,
        DocumentStatus.RETURNED,
        DocumentStatus.APPROVED,
    }

    @classmethod
    @transaction.atomic
    def mark(cls, now=None) -> int:
        now = now or timezone.now()
        overdue = (
            Document.objects.select_for_update()
            .exclude(status__in=[DocumentStatus.COMPLETED, DocumentStatus.ARCHIVED])
            .filter(responsible__isnull=False, deadline__lt=now)
            .select_related("author", "responsible")
        )
        marked = 0
        for document in overdue:
            previous_status = document.status
            key = (
                f"document_overdue:{document.id}:{document.responsible_id}:"
                f"{document.deadline.isoformat()}"
            )
            NotificationService.notify_many(
                [document.author, document.responsible],
                notification_type=NotificationType.DOCUMENT_OVERDUE,
                title="Документ просрочен",
                message=f"Срок по документу «{document.title}» истёк.",
                document=document,
                dedupe_key=key,
            )
            if previous_status in cls.OVERDUE_STATUSES:
                document.status_before_overdue = previous_status
                document.status = DocumentStatus.OVERDUE
                document.save(
                    update_fields=["status", "status_before_overdue", "updated_at"]
                )
                from apps.documents.services import HistoryService

                HistoryService.record(
                    document,
                    None,
                    "updated",
                    old_values={"status": previous_status},
                    new_values={"status": DocumentStatus.OVERDUE},
                    description="Документ автоматически отмечен просроченным",
                )
                marked += 1
        return marked


class NotificationCleanupService:
    @staticmethod
    def cleanup(now=None) -> int:
        now = now or timezone.now()
        cutoff = now - timedelta(days=settings.NOTIFICATION_RETENTION_DAYS)
        deleted, _ = Notification.objects.filter(
            is_read=True, created_at__lt=cutoff
        ).delete()
        return deleted


class DeadlineService:
    """Обратная совместимость для синхронного запуска обеих проверок."""

    @staticmethod
    def check(now=None) -> dict:
        return {
            "deadline_soon": UpcomingDeadlineService.check(now=now),
            "overdue": OverdueDocumentService.mark(now=now),
        }
