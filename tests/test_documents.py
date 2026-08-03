from datetime import timedelta

import pytest
from django.utils import timezone

from apps.documents.models import (
    Document,
    DocumentCategory,
    DocumentPriority,
    DocumentStatus,
)
from apps.organizations.models import Department

pytestmark = pytest.mark.django_db


@pytest.fixture
def document_category(admin, child_department):
    category = DocumentCategory.objects.create(
        name="Служебные записки",
        code="memos",
        retention_period_days=365,
        created_by=admin,
        updated_by=admin,
    )
    category.allowed_departments.add(child_department)
    return category


@pytest.fixture
def document(employee, child_department, document_category):
    return Document.objects.create(
        title="Запрос оборудования",
        description="Требуется новый компьютер",
        document_type="memo",
        category=document_category,
        author=employee,
        department=child_department,
        priority=DocumentPriority.HIGH,
        deadline=timezone.now() + timedelta(days=5),
    )


def document_payload(category, department, **overrides):
    payload = {
        "title": "Новый документ",
        "description": "Описание",
        "document_type": "memo",
        "category": str(category.id),
        "department": str(department.id),
        "priority": DocumentPriority.NORMAL,
    }
    payload.update(overrides)
    return payload


class TestDocumentCrud:
    def test_employee_creates_document_as_author(
        self, employee_client, employee, child_department, document_category
    ):
        response = employee_client.post(
            "/api/documents/",
            document_payload(document_category, child_department),
            format="json",
        )
        assert response.status_code == 201
        created = Document.objects.get(title="Новый документ")
        assert created.author == employee
        assert created.status == DocumentStatus.DRAFT

    def test_employee_cannot_create_for_another_department(
        self, employee_client, root_department, document_category
    ):
        response = employee_client.post(
            "/api/documents/",
            document_payload(document_category, root_department),
            format="json",
        )
        assert response.status_code == 400

    def test_inactive_category_rejected(
        self, employee_client, child_department, document_category
    ):
        document_category.status = "inactive"
        document_category.save(update_fields=["status"])
        response = employee_client.post(
            "/api/documents/",
            document_payload(document_category, child_department),
            format="json",
        )
        assert response.status_code == 400

    def test_author_edits_draft(self, employee_client, document):
        response = employee_client.patch(
            f"/api/documents/{document.id}/", {"title": "Изменено"}, format="json"
        )
        assert response.status_code == 200
        document.refresh_from_db()
        assert document.title == "Изменено"

    def test_submitted_document_cannot_be_edited(self, employee_client, document, manager):
        employee_client.post(
            f"/api/documents/{document.id}/submit/",
            {"approvers": [str(manager.id)]},
            format="json",
        )
        response = employee_client.patch(
            f"/api/documents/{document.id}/", {"title": "Нельзя"}, format="json"
        )
        assert response.status_code == 400

    def test_draft_delete_is_soft(self, employee_client, document):
        response = employee_client.delete(f"/api/documents/{document.id}/")
        assert response.status_code == 204
        assert not Document.objects.filter(pk=document.pk).exists()
        assert Document.all_objects.filter(pk=document.pk, is_deleted=True).exists()

    def test_submitted_document_cannot_be_deleted(self, employee_client, document, manager):
        employee_client.post(
            f"/api/documents/{document.id}/submit/",
            {"approvers": [str(manager.id)]},
            format="json",
        )
        response = employee_client.delete(f"/api/documents/{document.id}/")
        assert response.status_code == 400


class TestDocumentVisibility:
    def test_employee_does_not_see_another_users_document(
        self, auth_client, user_factory, child_department, document
    ):
        other = user_factory(department=child_department)
        response = auth_client(other).get(f"/api/documents/{document.id}/")
        assert response.status_code == 404

    def test_responsible_sees_document(
        self, auth_client, user_factory, child_department, document
    ):
        responsible = user_factory(department=child_department)
        document.responsible = responsible
        document.save(update_fields=["responsible"])
        response = auth_client(responsible).get(f"/api/documents/{document.id}/")
        assert response.status_code == 200

    def test_manager_sees_department_document(self, manager_client, document):
        assert manager_client.get(f"/api/documents/{document.id}/").status_code == 200

    def test_manager_does_not_see_other_department(
        self, manager_client, user_factory, root_department, document_category
    ):
        other_department = Department.objects.create(name="Финансы", code="finance")
        author = user_factory(department=other_department)
        other_document = Document.objects.create(
            title="Финансовый документ",
            document_type="memo",
            category=document_category,
            author=author,
            department=other_department,
        )
        assert manager_client.get(f"/api/documents/{other_document.id}/").status_code == 404

    def test_admin_sees_everything(self, admin_client, document):
        assert admin_client.get(f"/api/documents/{document.id}/").status_code == 200


class TestDocumentActions:
    def test_submit(self, employee_client, document, manager):
        response = employee_client.post(
            f"/api/documents/{document.id}/submit/",
            {"approvers": [str(manager.id)]},
            format="json",
        )
        assert response.status_code == 200
        document.refresh_from_db()
        assert document.status == DocumentStatus.IN_REVIEW
        assert document.submitted_at is not None

    def test_archive_and_restore(self, admin_client, document):
        document.status = DocumentStatus.COMPLETED
        document.completed_at = timezone.now()
        document.save(update_fields=["status", "completed_at"])

        archived = admin_client.post(f"/api/documents/{document.id}/archive/")
        assert archived.status_code == 200
        document.refresh_from_db()
        assert document.status == DocumentStatus.ARCHIVED

        restored = admin_client.post(f"/api/documents/{document.id}/restore/")
        assert restored.status_code == 200
        document.refresh_from_db()
        assert document.status == DocumentStatus.COMPLETED

    def test_employee_cannot_archive(self, employee_client, document):
        document.status = DocumentStatus.COMPLETED
        document.save(update_fields=["status"])
        assert employee_client.post(f"/api/documents/{document.id}/archive/").status_code == 403


class TestDocumentListsAndFilters:
    def test_my_documents(self, employee_client, document):
        response = employee_client.get("/api/documents/my/")
        assert response.status_code == 200
        assert response.json()["data"]["count"] == 1

    def test_status_and_priority_filters(self, employee_client, document):
        included = employee_client.get("/api/documents/?status=draft&priority=high")
        excluded = employee_client.get("/api/documents/?status=approved")
        assert included.json()["data"]["count"] == 1
        assert excluded.json()["data"]["count"] == 0

    def test_search_title(self, employee_client, document):
        response = employee_client.get("/api/documents/?search=оборудования")
        assert response.json()["data"]["count"] == 1

    def test_special_lists(self, employee_client, document):
        document.status = DocumentStatus.OVERDUE
        document.save(update_fields=["status"])
        assert employee_client.get("/api/documents/overdue/").json()["data"]["count"] == 1
        assert employee_client.get("/api/documents/returned/").json()["data"]["count"] == 0
