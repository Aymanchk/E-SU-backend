import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.documents.models import (
    Document,
    DocumentCategory,
    DocumentComment,
    DocumentCommentType,
    DocumentHistory,
    DocumentHistoryAction,
    DocumentStatus,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def local_file_storage(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }


@pytest.fixture
def history_category(admin):
    return DocumentCategory.objects.create(
        name="История",
        code="history",
        retention_period_days=365,
        created_by=admin,
        updated_by=admin,
    )


@pytest.fixture
def history_document(employee, child_department, history_category):
    return Document.objects.create(
        title="Документ с историей",
        document_type="memo",
        category=history_category,
        author=employee,
        department=child_department,
        responsible=employee,
    )


class TestDocumentComments:
    def test_create_list_update_and_delete(self, employee_client, history_document):
        created = employee_client.post(
            f"/api/documents/{history_document.id}/comments/",
            {"text": "Первый комментарий"},
            format="json",
        )
        assert created.status_code == 201
        comment_id = created.json()["data"]["id"]

        listed = employee_client.get(f"/api/documents/{history_document.id}/comments/")
        assert listed.json()["data"]["count"] == 1

        updated = employee_client.patch(
            f"/api/comments/{comment_id}/", {"text": "Исправлено"}, format="json"
        )
        assert updated.status_code == 200
        assert updated.json()["data"]["text"] == "Исправлено"

        deleted = employee_client.delete(f"/api/comments/{comment_id}/")
        assert deleted.status_code == 204
        assert not DocumentComment.objects.filter(pk=comment_id).exists()

    def test_empty_comment_rejected(self, employee_client, history_document):
        response = employee_client.post(
            f"/api/documents/{history_document.id}/comments/",
            {"text": "   "},
            format="json",
        )
        assert response.status_code == 400

    def test_other_user_cannot_edit_comment(
        self, auth_client, user_factory, child_department, history_document, employee
    ):
        other = user_factory(department=child_department)
        history_document.responsible = other
        history_document.save(update_fields=["responsible"])
        comment = DocumentComment.objects.create(
            document=history_document,
            author=employee,
            text="Чужой комментарий",
        )
        response = auth_client(other).patch(
            f"/api/comments/{comment.id}/", {"text": "Взлом"}, format="json"
        )
        assert response.status_code == 403

    @pytest.mark.parametrize(
        "comment_type",
        [DocumentCommentType.APPROVAL, DocumentCommentType.RETURN_REASON, DocumentCommentType.SYSTEM],
    )
    def test_non_general_comment_is_immutable(
        self, employee_client, history_document, employee, comment_type
    ):
        comment = DocumentComment.objects.create(
            document=history_document,
            author=employee,
            text="Служебный комментарий",
            comment_type=comment_type,
        )
        patch = employee_client.patch(
            f"/api/comments/{comment.id}/", {"text": "Изменение"}, format="json"
        )
        delete = employee_client.delete(f"/api/comments/{comment.id}/")
        assert patch.status_code == 400
        assert delete.status_code == 400

    def test_archived_document_rejects_new_comments(self, employee_client, history_document):
        history_document.status = DocumentStatus.ARCHIVED
        history_document.save(update_fields=["status"])
        response = employee_client.post(
            f"/api/documents/{history_document.id}/comments/",
            {"text": "Поздний комментарий"},
            format="json",
        )
        assert response.status_code == 400


class TestDocumentHistory:
    def test_create_and_update_are_recorded(
        self, employee_client, employee, child_department, history_category
    ):
        created = employee_client.post(
            "/api/documents/",
            {
                "title": "Новый исторический документ",
                "document_type": "memo",
                "category": str(history_category.id),
                "department": str(child_department.id),
            },
            format="json",
        )
        document_id = created.json()["data"]["id"]
        employee_client.patch(
            f"/api/documents/{document_id}/",
            {"title": "Новое название"},
            format="json",
        )

        entries = DocumentHistory.objects.filter(document_id=document_id)
        assert list(entries.values_list("action", flat=True)) == [
            DocumentHistoryAction.CREATED,
            DocumentHistoryAction.UPDATED,
        ]
        updated = entries.get(action=DocumentHistoryAction.UPDATED)
        assert updated.old_values["title"] == "Новый исторический документ"
        assert updated.new_values["title"] == "Новое название"

    def test_submit_approve_and_comments_are_recorded(
        self, employee_client, manager_client, history_document, manager
    ):
        employee_client.post(
            f"/api/documents/{history_document.id}/submit/",
            {"approvers": [str(manager.id)]},
            format="json",
        )
        manager_client.post(
            f"/api/documents/{history_document.id}/approve/",
            {"comment": "Согласовано"},
            format="json",
        )
        assert list(
            history_document.history.values_list("action", flat=True)
        ) == [DocumentHistoryAction.SUBMITTED, DocumentHistoryAction.APPROVED]
        assert history_document.comments.get().comment_type == DocumentCommentType.APPROVAL

    def test_return_and_resubmit_are_recorded(
        self, employee_client, manager_client, history_document, manager
    ):
        payload = {"approvers": [str(manager.id)]}
        employee_client.post(
            f"/api/documents/{history_document.id}/submit/", payload, format="json"
        )
        manager_client.post(
            f"/api/documents/{history_document.id}/return/",
            {"comment": "Исправить"},
            format="json",
        )
        employee_client.post(
            f"/api/documents/{history_document.id}/submit/", payload, format="json"
        )
        actions = list(history_document.history.values_list("action", flat=True))
        assert actions == [
            DocumentHistoryAction.SUBMITTED,
            DocumentHistoryAction.RETURNED,
            DocumentHistoryAction.RESUBMITTED,
        ]
        assert history_document.comments.get().comment_type == DocumentCommentType.RETURN_REASON

    def test_file_upload_and_delete_are_recorded(
        self, employee_client, history_document, django_capture_on_commit_callbacks
    ):
        uploaded = employee_client.post(
            f"/api/documents/{history_document.id}/files/",
            {
                "file": SimpleUploadedFile(
                    "history.pdf", b"%PDF-history", content_type="application/pdf"
                )
            },
            format="multipart",
        )
        file_id = uploaded.json()["data"]["id"]
        with django_capture_on_commit_callbacks(execute=True):
            employee_client.delete(f"/api/document-files/{file_id}/")
        assert list(history_document.history.values_list("action", flat=True)) == [
            DocumentHistoryAction.FILE_UPLOADED,
            DocumentHistoryAction.FILE_DELETED,
        ]

    def test_registration_completion_archive_and_restore_are_recorded(
        self, admin_client, employee_client, history_document
    ):
        history_document.status = DocumentStatus.APPROVED
        history_document.save(update_fields=["status"])
        admin_client.post(f"/api/documents/{history_document.id}/register/")
        employee_client.post(f"/api/documents/{history_document.id}/complete/")
        admin_client.post(f"/api/documents/{history_document.id}/archive/")
        admin_client.post(f"/api/documents/{history_document.id}/restore/")
        assert list(history_document.history.values_list("action", flat=True)) == [
            DocumentHistoryAction.REGISTERED,
            DocumentHistoryAction.COMPLETED,
            DocumentHistoryAction.ARCHIVED,
            DocumentHistoryAction.RESTORED,
        ]

    def test_history_endpoint_is_read_only(self, employee_client, history_document):
        response = employee_client.get(f"/api/documents/{history_document.id}/history/")
        assert response.status_code == 200
        assert employee_client.post(
            f"/api/documents/{history_document.id}/history/", {}, format="json"
        ).status_code == 405
