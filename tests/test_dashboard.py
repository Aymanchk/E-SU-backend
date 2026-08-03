from datetime import timedelta

import pytest
from django.utils import timezone

from apps.documents.models import (
    ApprovalRoute,
    ApprovalStep,
    ApprovalStepStatus,
    Document,
    DocumentCategory,
    DocumentHistory,
    DocumentHistoryAction,
    DocumentStatus,
)
from apps.documents.services import DashboardService
from apps.organizations.models import Department

pytestmark = pytest.mark.django_db


@pytest.fixture
def category(admin):
    return DocumentCategory.objects.create(
        name="Приказы",
        code="dashboard-orders",
        retention_period_days=365,
        created_by=admin,
        updated_by=admin,
    )


def create_document(category, author, department, **kwargs):
    defaults = {
        "title": "Документ Dashboard",
        "document_type": "order",
        "status": DocumentStatus.DRAFT,
        "deadline": timezone.now() + timedelta(days=3),
    }
    defaults.update(kwargs)
    return Document.objects.create(
        category=category,
        author=author,
        department=department,
        **defaults,
    )


class TestDashboardAccess:
    def test_employee_sees_only_authored_documents(
        self, employee_client, employee, manager, child_department, category
    ):
        own = create_document(
            category, employee, child_department, status=DocumentStatus.IN_REVIEW
        )
        create_document(
            category,
            manager,
            child_department,
            responsible=employee,
            status=DocumentStatus.RETURNED,
        )
        DocumentHistory.objects.create(
            document=own, user=employee, action=DocumentHistoryAction.CREATED
        )

        response = employee_client.get("/api/dashboard/")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_documents"] == 1
        assert data["in_review"] == 1
        assert data["returned"] == 0
        assert [item["id"] for item in data["recent_documents"]] == [str(own.id)]
        assert len(data["recent_actions"]) == 1

    def test_manager_sees_department_and_personal_approval_tasks(
        self, manager_client, manager, employee, child_department, category, user_factory
    ):
        other_department = Department.objects.create(name="Финансы", code="finance-dashboard")
        outsider = user_factory(department=other_department)
        department_document = create_document(category, employee, child_department)
        hidden_document = create_document(category, outsider, other_department)
        route = ApprovalRoute.objects.create(
            document=department_document, created_by=employee
        )
        ApprovalStep.objects.create(
            route=route,
            document=department_document,
            order=1,
            approver=manager,
            status=ApprovalStepStatus.CURRENT,
        )
        hidden_route = ApprovalRoute.objects.create(
            document=hidden_document, created_by=outsider
        )
        ApprovalStep.objects.create(
            route=hidden_route,
            document=hidden_document,
            order=1,
            approver=outsider,
            status=ApprovalStepStatus.CURRENT,
        )

        data = manager_client.get("/api/dashboard/").json()["data"]

        assert data["total_documents"] == 1
        assert data["approval_tasks"] == 1

    def test_admin_sees_global_statistics(
        self, admin_client, admin, employee, child_department, root_department, category
    ):
        create_document(
            category, employee, child_department, status=DocumentStatus.COMPLETED
        )
        create_document(category, admin, root_department, status=DocumentStatus.OVERDUE)

        data = admin_client.get("/api/dashboard/").json()["data"]

        assert data["total_documents"] == 2
        assert data["completed"] == 1
        assert data["overdue"] == 1


class TestDashboardContent:
    def test_limits_and_orders_dashboard_lists(
        self, employee_client, employee, child_department, category
    ):
        now = timezone.now()
        documents = [
            create_document(
                category,
                employee,
                child_department,
                title=f"Документ {index}",
                deadline=now + timedelta(days=7 - index),
            )
            for index in range(7)
        ]
        for document in documents:
            DocumentHistory.objects.create(
                document=document,
                user=employee,
                action=DocumentHistoryAction.CREATED,
            )
            DocumentHistory.objects.create(
                document=document,
                user=employee,
                action=DocumentHistoryAction.UPDATED,
            )

        data = employee_client.get("/api/dashboard/").json()["data"]

        assert len(data["recent_documents"]) == 5
        assert len(data["upcoming_deadlines"]) == 5
        assert len(data["recent_actions"]) == 10
        deadlines = [item["deadline"] for item in data["upcoming_deadlines"]]
        assert deadlines == sorted(deadlines)

    def test_service_has_bounded_query_count(
        self,
        django_assert_max_num_queries,
        employee,
        child_department,
        category,
    ):
        create_document(category, employee, child_department)

        with django_assert_max_num_queries(8):
            data = DashboardService.build(employee)
            list(data["recent_documents"])
            list(data["upcoming_deadlines"])
            list(data["recent_actions"])
