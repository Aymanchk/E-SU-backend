import pytest

from apps.documents.models import (
    ApprovalAction,
    ApprovalActionType,
    ApprovalRoute,
    ApprovalRouteStatus,
    ApprovalStepStatus,
    Document,
    DocumentCategory,
    DocumentStatus,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def approval_document(employee, admin, child_department):
    category = DocumentCategory.objects.create(
        name="На согласование",
        code="approval",
        retention_period_days=365,
        created_by=admin,
        updated_by=admin,
    )
    return Document.objects.create(
        title="Документ на согласование",
        document_type="memo",
        category=category,
        author=employee,
        department=child_department,
    )


@pytest.fixture
def second_manager(user_factory, child_department):
    return user_factory(email="manager2@esu.kg", role_code="manager", department=child_department)


def submit(client, document, *approvers):
    return client.post(
        f"/api/v1/documents/{document.id}/submit/",
        {"approvers": [str(approver.id) for approver in approvers]},
        format="json",
    )


class TestApprovalRouteCreation:
    def test_submit_creates_sequential_route(
        self, employee_client, approval_document, manager, second_manager
    ):
        response = submit(employee_client, approval_document, manager, second_manager)

        assert response.status_code == 200
        route = ApprovalRoute.objects.get(document=approval_document)
        steps = list(route.steps.all())
        assert [step.order for step in steps] == [1, 2]
        assert [step.status for step in steps] == [
            ApprovalStepStatus.CURRENT,
            ApprovalStepStatus.PENDING,
        ]
        approval_document.refresh_from_db()
        assert approval_document.status == DocumentStatus.IN_REVIEW
        assert approval_document.current_approval_step == 1

    def test_empty_and_duplicate_approvers_rejected(
        self, employee_client, approval_document, manager
    ):
        empty = submit(employee_client, approval_document)
        duplicate = submit(employee_client, approval_document, manager, manager)
        assert empty.status_code == 400
        assert duplicate.status_code == 400
        assert not ApprovalRoute.objects.exists()

    def test_only_author_can_submit(
        self,
        auth_client,
        user_factory,
        child_department,
        approval_document,
        manager,
    ):
        responsible = user_factory(department=child_department)
        approval_document.responsible = responsible
        approval_document.save(update_fields=["responsible"])
        response = submit(auth_client(responsible), approval_document, manager)
        assert response.status_code == 403


class TestSequentialApproval:
    def test_steps_activate_in_order_and_final_step_approves_document(
        self,
        employee_client,
        manager_client,
        auth_client,
        approval_document,
        manager,
        second_manager,
    ):
        submit(employee_client, approval_document, manager, second_manager)

        first = manager_client.post(
            f"/api/v1/documents/{approval_document.id}/approve/",
            {"comment": "Первый согласовал"},
            format="json",
        )
        assert first.status_code == 200
        approval_document.refresh_from_db()
        assert approval_document.status == DocumentStatus.IN_REVIEW
        assert approval_document.current_approval_step == 2

        second = auth_client(second_manager).post(
            f"/api/v1/documents/{approval_document.id}/approve/",
            {"comment": "Второй согласовал"},
            format="json",
        )
        assert second.status_code == 200
        approval_document.refresh_from_db()
        assert approval_document.status == DocumentStatus.APPROVED
        assert approval_document.approved_at is not None
        assert approval_document.current_approval_step is None
        assert ApprovalAction.objects.filter(action=ApprovalActionType.APPROVE).count() == 2

    def test_non_current_approver_cannot_approve(
        self,
        employee_client,
        auth_client,
        approval_document,
        manager,
        second_manager,
    ):
        submit(employee_client, approval_document, manager, second_manager)
        response = auth_client(second_manager).post(
            f"/api/v1/documents/{approval_document.id}/approve/", {}, format="json"
        )
        assert response.status_code == 403

    def test_for_approval_contains_only_current_step(
        self,
        employee_client,
        manager_client,
        auth_client,
        approval_document,
        manager,
        second_manager,
    ):
        submit(employee_client, approval_document, manager, second_manager)
        first_count = manager_client.get("/api/v1/documents/for-approval/").json()["data"]["count"]
        second_count = (
            auth_client(second_manager)
            .get("/api/v1/documents/for-approval/")
            .json()["data"]["count"]
        )
        assert first_count == 1
        assert second_count == 0


class TestApprovalReturn:
    def test_return_requires_comment(
        self, employee_client, manager_client, approval_document, manager
    ):
        submit(employee_client, approval_document, manager)
        response = manager_client.post(
            f"/api/v1/documents/{approval_document.id}/return/", {}, format="json"
        )
        assert response.status_code == 400

    def test_return_changes_document_and_route_status(
        self, employee_client, manager_client, approval_document, manager, second_manager
    ):
        submit(employee_client, approval_document, manager, second_manager)
        response = manager_client.post(
            f"/api/v1/documents/{approval_document.id}/return/",
            {"comment": "Исправьте реквизиты"},
            format="json",
        )
        assert response.status_code == 200
        approval_document.refresh_from_db()
        route = ApprovalRoute.objects.get()
        assert approval_document.status == DocumentStatus.RETURNED
        assert route.status == ApprovalRouteStatus.RETURNED
        assert route.steps.get(order=1).status == ApprovalStepStatus.RETURNED
        assert route.steps.get(order=2).status == ApprovalStepStatus.CANCELLED
        action = ApprovalAction.objects.get(action=ApprovalActionType.RETURN)
        assert action.comment == "Исправьте реквизиты"

    def test_resubmit_starts_new_route(
        self, employee_client, manager_client, approval_document, manager, second_manager
    ):
        submit(employee_client, approval_document, manager)
        manager_client.post(
            f"/api/v1/documents/{approval_document.id}/return/",
            {"comment": "На доработку"},
            format="json",
        )

        response = submit(employee_client, approval_document, second_manager)
        assert response.status_code == 200
        assert ApprovalRoute.objects.filter(document=approval_document).count() == 2
        newest = ApprovalRoute.objects.filter(document=approval_document).first()
        assert newest.status == ApprovalRouteStatus.ACTIVE
        assert newest.steps.get().status == ApprovalStepStatus.CURRENT

    def test_approval_endpoint_returns_steps_and_actions(
        self, employee_client, manager_client, approval_document, manager
    ):
        submit(employee_client, approval_document, manager)
        manager_client.post(f"/api/v1/documents/{approval_document.id}/approve/", {}, format="json")
        response = employee_client.get(f"/api/v1/documents/{approval_document.id}/approval/")
        assert response.status_code == 200
        assert len(response.json()["data"]["steps"]) == 1
        assert len(response.json()["data"]["actions"]) == 1
