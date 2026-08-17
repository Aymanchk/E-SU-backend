from datetime import timedelta

import pytest
from django.utils import timezone

from apps.documents.models import (
    ApprovalRoute,
    ApprovalStep,
    ApprovalStepStatus,
    Document,
    DocumentCategory,
    DocumentStatus,
)
from apps.documents.serializers import DashboardSerializer
from apps.documents.services import DashboardService
from apps.notifications.models import NotificationType
from apps.notifications.services import NotificationService
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
    def test_employee_sees_authored_and_responsible_documents(
        self, employee_client, employee, manager, child_department, category
    ):
        own = create_document(
            category, employee, child_department, status=DocumentStatus.IN_REVIEW
        )
        responsible_document = create_document(
            category,
            manager,
            child_department,
            responsible=employee,
            status=DocumentStatus.RETURNED,
        )
        response = employee_client.get("/api/v1/dashboard/")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["counters"] == {
            "all": 2,
            "my": 1,
            "for_approval": 0,
            "returned": 1,
            "overdue": 0,
            "archived": 0,
        }
        assert {item["id"] for item in data["recent_documents"]} == {
            str(own.id),
            str(responsible_document.id),
        }

    def test_manager_sees_department_and_personal_approval_tasks(
        self, manager_client, manager, employee, child_department, category, user_factory
    ):
        other_department = Department.objects.create(name="Финансы", code="finance-dashboard")
        outsider = user_factory(department=other_department)
        department_document = create_document(category, employee, child_department)
        hidden_document = create_document(category, outsider, other_department)
        route = ApprovalRoute.objects.create(document=department_document, created_by=employee)
        ApprovalStep.objects.create(
            route=route,
            document=department_document,
            order=1,
            approver=manager,
            status=ApprovalStepStatus.CURRENT,
        )
        hidden_route = ApprovalRoute.objects.create(document=hidden_document, created_by=outsider)
        ApprovalStep.objects.create(
            route=hidden_route,
            document=hidden_document,
            order=1,
            approver=outsider,
            status=ApprovalStepStatus.CURRENT,
        )

        data = manager_client.get("/api/v1/dashboard/").json()["data"]

        assert data["counters"]["all"] == 1
        assert data["counters"]["for_approval"] == 1
        assert [item["id"] for item in data["approval_documents"]] == [
            str(department_document.id)
        ]

    def test_admin_sees_global_statistics(
        self, admin_client, admin, employee, child_department, root_department, category
    ):
        create_document(category, employee, child_department, status=DocumentStatus.COMPLETED)
        create_document(category, admin, root_department, status=DocumentStatus.OVERDUE)

        data = admin_client.get("/api/v1/dashboard/").json()["data"]

        assert data["counters"]["all"] == 2
        assert data["counters"]["my"] == 1
        assert data["counters"]["overdue"] == 1


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
        NotificationService.create(
            recipient=employee,
            notification_type=NotificationType.COMMENT_ADDED,
            title="Dashboard",
            message="Новое событие",
            document=documents[0],
            send_email=False,
        )

        data = employee_client.get("/api/v1/dashboard/").json()["data"]

        assert len(data["recent_documents"]) == 5
        assert data["approval_documents"] == []
        assert len(data["recent_notifications"]) == 1
        assert data["quick_actions"][0]["code"] == "create_document"

    def test_service_has_bounded_query_count(
        self,
        django_assert_max_num_queries,
        employee,
        child_department,
        category,
    ):
        create_document(category, employee, child_department)

        with django_assert_max_num_queries(9):
            data = DashboardService.build(employee)
            serialized = DashboardSerializer(data).data
        assert serialized["counters"]["all"] == 1
