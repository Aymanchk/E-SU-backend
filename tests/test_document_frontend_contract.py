from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import UserStatus
from apps.documents.models import Document, DocumentCategory, DocumentPriority

pytestmark = pytest.mark.django_db


@pytest.fixture
def frontend_category(admin, child_department):
    category = DocumentCategory.objects.create(
        name="Frontend категория",
        code="frontend-category",
        retention_period_days=365,
        created_by=admin,
        updated_by=admin,
    )
    category.allowed_departments.add(child_department)
    return category


def frontend_payload(category, department, responsible=None, **overrides):
    payload = {
        "title": "Документ frontend",
        "description": "Описание",
        "document_type": "order",
        "category_id": str(category.id),
        "department_id": str(department.id),
        "responsible_id": str(responsible.id) if responsible else None,
        "priority": DocumentPriority.NORMAL,
        "deadline": (timezone.now() + timedelta(days=5)).isoformat(),
    }
    payload.update(overrides)
    return payload


def test_create_accepts_frontend_id_fields(
    employee_client, employee, manager, child_department, frontend_category
):
    response = employee_client.post(
        "/api/v1/documents/",
        frontend_payload(frontend_category, child_department, manager),
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["data"]["category_id"] == str(frontend_category.id)
    assert response.json()["data"]["department_id"] == str(child_department.id)
    assert response.json()["data"]["responsible_id"] == str(manager.id)
    document = Document.objects.get()
    assert document.author == employee
    assert document.responsible == manager


def test_legacy_relation_names_remain_temporarily_supported(
    employee_client, child_department, frontend_category
):
    payload = frontend_payload(frontend_category, child_department)
    payload["category"] = payload.pop("category_id")
    payload["department"] = payload.pop("department_id")
    payload["responsible"] = payload.pop("responsible_id")

    response = employee_client.post("/api/documents/", payload, format="json")

    assert response.status_code == 201


def test_conflicting_legacy_and_canonical_fields_are_rejected(
    employee_client, root_department, child_department, frontend_category
):
    payload = frontend_payload(frontend_category, child_department)
    payload["department"] = str(root_department.id)

    response = employee_client.post("/api/v1/documents/", payload, format="json")

    assert response.status_code == 400
    assert "department_id" in response.json()["error"]["details"]


def test_deadline_in_past_is_rejected(
    employee_client, child_department, frontend_category
):
    payload = frontend_payload(
        frontend_category,
        child_department,
        deadline=(timezone.now() - timedelta(minutes=1)).isoformat(),
    )

    response = employee_client.post("/api/v1/documents/", payload, format="json")

    assert response.status_code == 400
    assert "deadline" in response.json()["error"]["details"]


@pytest.mark.parametrize(
    ("status", "is_active"),
    [(UserStatus.BLOCKED, True), (UserStatus.ACTIVE, False)],
)
def test_inactive_responsible_is_rejected(
    employee_client,
    user_factory,
    child_department,
    frontend_category,
    status,
    is_active,
):
    responsible = user_factory(
        department=child_department, status=status, is_active=is_active
    )

    response = employee_client.post(
        "/api/v1/documents/",
        frontend_payload(frontend_category, child_department, responsible),
        format="json",
    )

    assert response.status_code == 400
    assert "responsible_id" in response.json()["error"]["details"]


@pytest.mark.parametrize(
    "ordering",
    [
        "created_at",
        "updated_at",
        "deadline",
        "title",
        "priority",
        "status",
        "registration_number",
    ],
)
def test_document_ordering_fields_supported(
    employee_client, employee, child_department, frontend_category, ordering
):
    for index in range(2):
        Document.objects.create(
            title=f"Документ {index}",
            document_type="order",
            category=frontend_category,
            author=employee,
            department=child_department,
            deadline=timezone.now() + timedelta(days=index + 1),
        )

    response = employee_client.get(f"/api/v1/documents/?ordering={ordering}")

    assert response.status_code == 200
    assert response.json()["data"]["count"] == 2


def test_special_lists_reuse_filters_and_pagination(
    employee_client, employee, child_department, frontend_category
):
    for index in range(3):
        Document.objects.create(
            title=f"Приказ {index}",
            document_type="order",
            category=frontend_category,
            author=employee,
            department=child_department,
            priority=DocumentPriority.HIGH if index < 2 else DocumentPriority.LOW,
        )

    response = employee_client.get(
        "/api/v1/documents/my/?priority=high&page_size=1"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["count"] == 2
    assert len(data["results"]) == 1
