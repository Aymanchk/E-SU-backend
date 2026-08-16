import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.common.exceptions import StructuredAPIException
from apps.documents.models import Document, DocumentCategory, DocumentStatus
from apps.documents.services import DocumentService
from apps.documents.transitions import DocumentStateMachine, DocumentTransitionAction

pytestmark = pytest.mark.django_db


@pytest.fixture
def transition_document(admin, employee, child_department):
    category = DocumentCategory.objects.create(
        name="Категория переходов",
        code="transition-category",
        retention_period_days=365,
        created_by=admin,
        updated_by=admin,
    )
    return Document.objects.create(
        title="Документ переходов",
        document_type="memo",
        category=category,
        author=employee,
        responsible=employee,
        department=child_department,
    )


@pytest.mark.parametrize(
    ("current_status", "action", "target_status"),
    [
        (DocumentStatus.DRAFT, DocumentTransitionAction.SUBMIT, DocumentStatus.IN_REVIEW),
        (
            DocumentStatus.RETURNED,
            DocumentTransitionAction.RESUBMIT,
            DocumentStatus.IN_REVIEW,
        ),
        (
            DocumentStatus.IN_REVIEW,
            DocumentTransitionAction.APPROVE,
            DocumentStatus.APPROVED,
        ),
        (
            DocumentStatus.IN_REVIEW,
            DocumentTransitionAction.RETURN,
            DocumentStatus.RETURNED,
        ),
        (
            DocumentStatus.APPROVED,
            DocumentTransitionAction.COMPLETE,
            DocumentStatus.COMPLETED,
        ),
        (
            DocumentStatus.COMPLETED,
            DocumentTransitionAction.ARCHIVE,
            DocumentStatus.ARCHIVED,
        ),
        (
            DocumentStatus.ARCHIVED,
            DocumentTransitionAction.RESTORE,
            DocumentStatus.COMPLETED,
        ),
    ],
)
def test_allowed_transition_matrix(
    transition_document, current_status, action, target_status
):
    transition_document.status = current_status

    assert DocumentStateMachine.target_status(transition_document, action) == target_status


@pytest.mark.parametrize(
    ("current_status", "action"),
    [
        (DocumentStatus.APPROVED, DocumentTransitionAction.SUBMIT),
        (DocumentStatus.DRAFT, DocumentTransitionAction.RESUBMIT),
        (DocumentStatus.DRAFT, DocumentTransitionAction.APPROVE),
        (DocumentStatus.COMPLETED, DocumentTransitionAction.RETURN),
        (DocumentStatus.DRAFT, DocumentTransitionAction.COMPLETE),
        (DocumentStatus.DRAFT, DocumentTransitionAction.ARCHIVE),
        (DocumentStatus.COMPLETED, DocumentTransitionAction.RESTORE),
    ],
)
def test_invalid_transition_has_structured_details(
    transition_document, current_status, action
):
    transition_document.status = current_status

    with pytest.raises(StructuredAPIException) as error:
        DocumentStateMachine.target_status(transition_document, action)

    assert error.value.error_code == "invalid_document_transition"
    assert error.value.error_details == {
        "current_status": current_status,
        "requested_action": action,
    }


def test_invalid_transition_api_contract(admin_client, transition_document):
    response = admin_client.post(
        f"/api/v1/documents/{transition_document.id}/archive/"
    )

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "invalid_document_transition",
        "message": "Документ нельзя архивировать из текущего статуса",
        "details": {
            "current_status": DocumentStatus.DRAFT,
            "requested_action": DocumentTransitionAction.ARCHIVE,
        },
    }


def test_complete_locks_document_row(employee, transition_document):
    transition_document.status = DocumentStatus.APPROVED
    transition_document.save(update_fields=["status"])

    with CaptureQueriesContext(connection) as queries:
        DocumentService.complete(transition_document, employee)

    assert any("FOR UPDATE" in query["sql"].upper() for query in queries.captured_queries)
    transition_document.refresh_from_db()
    assert transition_document.status == DocumentStatus.COMPLETED
