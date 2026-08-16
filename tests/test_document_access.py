from types import SimpleNamespace

import pytest

from apps.common.permissions import HasPermissionPerAction
from apps.documents.access import DocumentAccessService
from apps.documents.models import (
    ApprovalRoute,
    ApprovalStep,
    ApprovalStepStatus,
    Document,
    DocumentCategory,
    DocumentStatus,
)
from apps.documents.views import DocumentViewSet
from apps.organizations.models import Department

pytestmark = pytest.mark.django_db


@pytest.fixture
def access_document(admin, employee, child_department):
    category = DocumentCategory.objects.create(
        name="Категория доступа",
        code="access-category",
        retention_period_days=365,
        created_by=admin,
        updated_by=admin,
    )
    return Document.objects.create(
        title="Документ доступа",
        document_type="memo",
        category=category,
        author=employee,
        department=child_department,
    )


def test_document_permission_map_is_complete():
    expected_actions = {
        "create",
        "list",
        "retrieve",
        "update",
        "partial_update",
        "destroy",
        "my",
        "for_approval",
        "returned",
        "overdue",
        "archive_list",
        "submit",
        "approve",
        "return_document",
        "register",
        "complete",
        "archive",
        "restore",
        "files",
        "comments",
        "history",
        "approval",
    }

    assert set(DocumentViewSet.permission_map) == expected_actions


def test_unmapped_action_is_denied(employee):
    request = SimpleNamespace(user=employee)
    view = SimpleNamespace(action="unmapped", permission_map={"list": None})

    assert HasPermissionPerAction().has_permission(request, view) is False


class TestDocumentAccessService:
    def test_author_access_to_draft(self, employee, access_document):
        assert DocumentAccessService.can_view(employee, access_document)
        assert DocumentAccessService.can_edit(employee, access_document)
        assert DocumentAccessService.can_delete(employee, access_document)
        assert DocumentAccessService.can_submit(employee, access_document)
        assert DocumentAccessService.can_upload_file(employee, access_document)
        assert DocumentAccessService.can_download_file(employee, access_document)
        assert DocumentAccessService.can_delete_file(employee, access_document)
        assert DocumentAccessService.can_comment(employee, access_document)
        assert DocumentAccessService.can_view_history(employee, access_document)

    def test_unrelated_employee_has_no_access(
        self, user_factory, child_department, access_document
    ):
        outsider = user_factory(department=child_department)

        assert not DocumentAccessService.can_view(outsider, access_document)
        assert not DocumentAccessService.can_edit(outsider, access_document)
        assert not DocumentAccessService.can_delete(outsider, access_document)
        assert not DocumentAccessService.can_submit(outsider, access_document)
        assert not DocumentAccessService.can_download_file(outsider, access_document)
        assert not DocumentAccessService.can_comment(outsider, access_document)

    def test_responsible_can_view_and_complete(
        self, user_factory, child_department, access_document
    ):
        responsible = user_factory(department=child_department)
        access_document.responsible = responsible
        access_document.status = DocumentStatus.APPROVED
        access_document.save(update_fields=["responsible", "status"])

        assert DocumentAccessService.can_view(responsible, access_document)
        assert DocumentAccessService.can_complete(responsible, access_document)
        assert not DocumentAccessService.can_edit(responsible, access_document)

    def test_manager_sees_only_own_department(
        self, manager, employee, admin, access_document
    ):
        other_department = Department.objects.create(
            name="Другое подразделение", code="other-access"
        )
        other_category = DocumentCategory.objects.create(
            name="Другая категория",
            code="other-access-category",
            retention_period_days=365,
            created_by=admin,
            updated_by=admin,
        )
        hidden = Document.objects.create(
            title="Чужой документ",
            document_type="memo",
            category=other_category,
            author=employee,
            department=other_department,
        )

        assert DocumentAccessService.can_view(manager, access_document)
        assert not DocumentAccessService.can_view(manager, hidden)

    def test_only_current_assigned_approver_can_act(
        self, manager, employee, user_factory, child_department, access_document
    ):
        second_approver = user_factory(role_code="manager", department=child_department)
        access_document.status = DocumentStatus.IN_REVIEW
        access_document.save(update_fields=["status"])
        route = ApprovalRoute.objects.create(
            document=access_document, created_by=employee
        )
        ApprovalStep.objects.create(
            route=route,
            document=access_document,
            order=1,
            approver=manager,
            status=ApprovalStepStatus.CURRENT,
        )
        ApprovalStep.objects.create(
            route=route,
            document=access_document,
            order=2,
            approver=second_approver,
            status=ApprovalStepStatus.PENDING,
        )

        assert DocumentAccessService.can_approve(manager, access_document)
        assert DocumentAccessService.can_return(manager, access_document)
        assert not DocumentAccessService.can_approve(second_approver, access_document)
        assert not DocumentAccessService.can_return(second_approver, access_document)

    def test_office_register_archive_and_restore_permissions(
        self, user_factory, child_department, access_document
    ):
        office = user_factory(role_code="office", department=child_department)

        access_document.status = DocumentStatus.APPROVED
        access_document.save(update_fields=["status"])
        assert DocumentAccessService.can_register(office, access_document)
        assert not DocumentAccessService.can_archive(office, access_document)

        access_document.status = DocumentStatus.COMPLETED
        access_document.save(update_fields=["status"])
        assert DocumentAccessService.can_archive(office, access_document)

        access_document.status = DocumentStatus.ARCHIVED
        access_document.save(update_fields=["status"])
        assert DocumentAccessService.can_restore(office, access_document)
        assert not DocumentAccessService.can_comment(office, access_document)


@pytest.mark.parametrize(
    ("method", "suffix"),
    [
        ("get", ""),
        ("patch", ""),
        ("delete", ""),
        ("post", "submit/"),
        ("get", "files/"),
        ("get", "comments/"),
        ("get", "history/"),
        ("get", "approval/"),
    ],
)
def test_foreign_document_uuid_does_not_leak_data(
    auth_client,
    user_factory,
    child_department,
    access_document,
    method,
    suffix,
):
    outsider = user_factory(department=child_department)
    client = auth_client(outsider)
    request = getattr(client, method)
    response = request(f"/api/v1/documents/{access_document.id}/{suffix}", {}, format="json")

    assert response.status_code == 404
