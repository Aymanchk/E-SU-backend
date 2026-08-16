from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from apps.documents.models import Document, DocumentCategory, DocumentStatus
from apps.notifications.models import Notification, NotificationType
from apps.notifications.services import (
    DeadlineService,
    NotificationCleanupService,
    NotificationService,
)
from apps.notifications.tasks import (
    check_upcoming_document_deadlines,
    cleanup_old_notifications,
    mark_overdue_documents,
    send_notification_email,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def notification_category(admin):
    return DocumentCategory.objects.create(
        name="Уведомления",
        code="notifications",
        retention_period_days=365,
        created_by=admin,
        updated_by=admin,
    )


@pytest.fixture
def notification_document(employee, child_department, notification_category):
    return Document.objects.create(
        title="Документ с уведомлениями",
        document_type="memo",
        category=notification_category,
        author=employee,
        department=child_department,
        responsible=employee,
    )


def create_notification(recipient, document=None, **overrides):
    defaults = {
        "recipient": recipient,
        "notification_type": NotificationType.COMMENT_ADDED,
        "title": "Новое уведомление",
        "message": "Текст уведомления",
        "document": document,
        "send_email": False,
    }
    defaults.update(overrides)
    return NotificationService.create(**defaults)


class TestNotificationApi:
    def test_list_contains_only_current_users_notifications(
        self, employee_client, employee, manager, notification_document
    ):
        own = create_notification(employee, notification_document)
        create_notification(manager, notification_document)

        response = employee_client.get("/api/v1/notifications/")
        ids = [item["id"] for item in response.json()["data"]["results"]]
        assert ids == [str(own.id)]

    def test_unread_count_and_read(self, employee_client, employee, notification_document):
        notification = create_notification(employee, notification_document)
        assert employee_client.get("/api/v1/notifications/unread-count/").json()["data"] == {
            "count": 1
        }

        response = employee_client.post(f"/api/v1/notifications/{notification.id}/read/")
        assert response.status_code == 200
        notification.refresh_from_db()
        assert notification.is_read is True
        assert notification.read_at is not None

    def test_read_all(self, employee_client, employee, notification_document):
        create_notification(employee, notification_document)
        create_notification(
            employee,
            notification_document,
            notification_type=NotificationType.DOCUMENT_APPROVED,
        )
        response = employee_client.post("/api/v1/notifications/read-all/")
        assert response.json()["data"]["updated"] == 2
        assert not Notification.objects.filter(recipient=employee, is_read=False).exists()

    def test_cannot_read_another_users_notification(
        self, employee_client, manager, notification_document
    ):
        notification = create_notification(manager, notification_document)
        response = employee_client.post(f"/api/v1/notifications/{notification.id}/read/")
        assert response.status_code == 404

    def test_filters(self, employee_client, employee, notification_document):
        create_notification(employee, notification_document)
        approved = create_notification(
            employee,
            notification_document,
            notification_type=NotificationType.DOCUMENT_APPROVED,
        )
        NotificationService.mark_read(approved)
        response = employee_client.get("/api/v1/notifications/?type=document_approved&is_read=true")
        assert response.json()["data"]["count"] == 1


class TestNotificationService:
    def test_dedupe_key_prevents_duplicates(self, employee, notification_document):
        for _ in range(2):
            create_notification(
                employee,
                notification_document,
                dedupe_key="same-event",
            )
        assert Notification.objects.filter(dedupe_key="same-event").count() == 1

    def test_email_task(self, settings, employee, notification_document):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        notification = create_notification(employee, notification_document)
        send_notification_email.run(str(notification.id))
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [employee.email]
        assert "E-SU" in mail.outbox[0].subject


class TestDeadlineService:
    def test_deadline_soon_is_not_duplicated(self, employee, notification_document):
        now = timezone.now()
        notification_document.deadline = now + timedelta(hours=12)
        notification_document.save(update_fields=["deadline"])

        first = DeadlineService.check(now=now)
        second = DeadlineService.check(now=now)
        assert first == {"deadline_soon": 1, "overdue": 0}
        assert second == {"deadline_soon": 0, "overdue": 0}
        assert Notification.objects.filter(
            type=NotificationType.DEADLINE_APPROACHING
        ).count() == 1

    def test_overdue_changes_allowed_status(self, employee, notification_document):
        now = timezone.now()
        notification_document.deadline = now - timedelta(minutes=1)
        notification_document.save(update_fields=["deadline"])
        DeadlineService.check(now=now)

        notification_document.refresh_from_db()
        assert notification_document.status == DocumentStatus.OVERDUE
        assert notification_document.status_before_overdue == DocumentStatus.DRAFT
        assert Notification.objects.filter(type=NotificationType.DOCUMENT_OVERDUE).count() == 1
        assert notification_document.history.filter(
            description="Документ автоматически отмечен просроченным"
        ).count() == 1

    def test_in_review_is_not_changed_to_overdue(self, employee, notification_document):
        now = timezone.now()
        notification_document.deadline = now - timedelta(minutes=1)
        notification_document.status = DocumentStatus.IN_REVIEW
        notification_document.save(update_fields=["deadline", "status"])
        DeadlineService.check(now=now)

        notification_document.refresh_from_db()
        assert notification_document.status == DocumentStatus.IN_REVIEW
        assert Notification.objects.filter(type=NotificationType.DOCUMENT_OVERDUE).exists()

    def test_overdue_notifies_author_and_responsible(
        self, user_factory, child_department, notification_document
    ):
        responsible = user_factory(department=child_department)
        notification_document.responsible = responsible
        notification_document.deadline = timezone.now() - timedelta(minutes=1)
        notification_document.save(update_fields=["responsible", "deadline"])

        DeadlineService.check()
        DeadlineService.check()

        notifications = Notification.objects.filter(
            document=notification_document,
            type=NotificationType.DOCUMENT_OVERDUE,
        )
        assert set(notifications.values_list("recipient_id", flat=True)) == {
            notification_document.author_id,
            responsible.id,
        }
        assert notifications.count() == 2

    def test_repeated_overdue_check_does_not_duplicate_history(
        self, notification_document
    ):
        now = timezone.now()
        notification_document.deadline = now - timedelta(minutes=1)
        notification_document.save(update_fields=["deadline"])

        DeadlineService.check(now=now)
        DeadlineService.check(now=now)

        assert notification_document.history.filter(
            description="Документ автоматически отмечен просроченным"
        ).count() == 1


class TestPeriodicTasks:
    def test_deadline_tasks(self, notification_document):
        notification_document.deadline = timezone.now() + timedelta(hours=12)
        notification_document.save(update_fields=["deadline"])
        assert check_upcoming_document_deadlines.run() == 1

        notification_document.deadline = timezone.now() - timedelta(minutes=1)
        notification_document.save(update_fields=["deadline"])
        assert mark_overdue_documents.run() == 1

    def test_cleanup_deletes_only_old_read_notifications(
        self, settings, employee, notification_document
    ):
        settings.NOTIFICATION_RETENTION_DAYS = 30
        old_read = create_notification(employee, notification_document)
        old_unread = create_notification(
            employee,
            notification_document,
            notification_type=NotificationType.DOCUMENT_APPROVED,
        )
        NotificationService.mark_read(old_read)
        old_date = timezone.now() - timedelta(days=31)
        Notification.objects.filter(pk__in=[old_read.pk, old_unread.pk]).update(
            created_at=old_date
        )

        assert NotificationCleanupService.cleanup() == 1
        assert not Notification.objects.filter(pk=old_read.pk).exists()
        assert Notification.objects.filter(pk=old_unread.pk).exists()

    def test_cleanup_task(self, settings):
        settings.NOTIFICATION_RETENTION_DAYS = 30
        assert cleanup_old_notifications.run() == 0


class TestNotificationIntegrations:
    def test_submit_and_approve_create_notifications(
        self,
        employee_client,
        manager_client,
        employee,
        manager,
        notification_document,
    ):
        employee_client.post(
            f"/api/v1/documents/{notification_document.id}/submit/",
            {"approvers": [str(manager.id)]},
            format="json",
        )
        assert Notification.objects.filter(
            recipient=manager, type=NotificationType.APPROVAL_REQUIRED
        ).exists()
        assert Notification.objects.filter(
            recipient=employee, type=NotificationType.DOCUMENT_SUBMITTED
        ).exists()

        manager_client.post(f"/api/v1/documents/{notification_document.id}/approve/", {})
        assert Notification.objects.filter(
            recipient=employee, type=NotificationType.DOCUMENT_APPROVED
        ).exists()

    def test_comment_notifies_other_participant(
        self,
        employee_client,
        user_factory,
        child_department,
        notification_document,
    ):
        responsible = user_factory(department=child_department)
        notification_document.responsible = responsible
        notification_document.save(update_fields=["responsible"])
        employee_client.post(
            f"/api/v1/documents/{notification_document.id}/comments/",
            {"text": "Новый комментарий"},
            format="json",
        )
        assert Notification.objects.filter(
            recipient=responsible, type=NotificationType.COMMENT_ADDED
        ).exists()

    def test_registration_notifies_author_and_responsible_once(
        self,
        admin_client,
        employee,
        user_factory,
        child_department,
        notification_document,
    ):
        responsible = user_factory(department=child_department)
        notification_document.responsible = responsible
        notification_document.status = DocumentStatus.APPROVED
        notification_document.save(update_fields=["responsible", "status"])

        first = admin_client.post(
            f"/api/documents/{notification_document.id}/register/"
        )
        second = admin_client.post(
            f"/api/documents/{notification_document.id}/register/"
        )

        assert first.status_code == 200
        assert second.status_code == 400
        notifications = Notification.objects.filter(
            document=notification_document,
            type=NotificationType.DOCUMENT_REGISTERED,
        )
        assert set(notifications.values_list("recipient_id", flat=True)) == {
            employee.id,
            responsible.id,
        }
        assert notifications.count() == 2
