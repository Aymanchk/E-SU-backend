import pytest

from apps.documents.models import (
    ApprovalRoute,
    ApprovalRouteSource,
    ApprovalRouteTemplate,
    ApprovalRouteTemplateStep,
    ApprovalTemplateApproverType,
    ApprovalTemplateDepartmentRelation,
    Document,
    DocumentCategory,
    DocumentStatus,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def second_manager(user_factory, child_department):
    return user_factory(
        email="template-manager2@esu.kg",
        role_code="manager",
        department=child_department,
    )


@pytest.fixture
def template_document(admin, employee, child_department):
    category = DocumentCategory.objects.create(
        name="Автоматическое согласование",
        code="automatic-approval",
        retention_period_days=365,
        created_by=admin,
        updated_by=admin,
    )
    document = Document.objects.create(
        title="Документ по шаблону",
        document_type="memo",
        category=category,
        author=employee,
        department=child_department,
    )
    return document


def create_template(category, admin, steps):
    template = ApprovalRouteTemplate.objects.create(
        category=category,
        name="Маршрут категории",
        created_by=admin,
        updated_by=admin,
    )
    for order, step in enumerate(steps, start=1):
        ApprovalRouteTemplateStep.objects.create(
            template=template, order=order, **step
        )
    return template


def test_template_resolves_all_approver_types(
    employee_client,
    user_factory,
    roles,
    admin,
    manager,
    child_department,
    template_document,
):
    office = user_factory(role_code="office", department=child_department)
    responsible = user_factory(department=child_department)
    template_document.responsible = responsible
    template_document.save(update_fields=["responsible"])
    child_department.manager = manager
    child_department.save(update_fields=["manager"])
    template = create_template(
        template_document.category,
        admin,
        [
            {
                "approver_type": ApprovalTemplateApproverType.DEPARTMENT_MANAGER,
                "department_relation": ApprovalTemplateDepartmentRelation.DOCUMENT_DEPARTMENT,
            },
            {
                "approver_type": ApprovalTemplateApproverType.ROLE,
                "role": roles["office"],
            },
            {
                "approver_type": ApprovalTemplateApproverType.SPECIFIC_USER,
                "specific_user": admin,
            },
            {
                "approver_type": ApprovalTemplateApproverType.DOCUMENT_RESPONSIBLE,
            },
        ],
    )

    response = employee_client.post(
        f"/api/v1/documents/{template_document.id}/submit/", {}, format="json"
    )

    assert response.status_code == 200
    route = ApprovalRoute.objects.get()
    assert route.source == ApprovalRouteSource.CATEGORY_TEMPLATE
    assert route.template == template
    assert list(route.steps.values_list("approver_id", flat=True)) == [
        manager.id,
        office.id,
        admin.id,
        responsible.id,
    ]
    assert route.template_snapshot["template_id"] == str(template.id)
    assert len(route.template_snapshot["steps"]) == 4


def test_manual_approvers_have_priority_over_template(
    employee_client, admin, manager, second_manager, template_document
):
    create_template(
        template_document.category,
        admin,
        [
            {
                "approver_type": ApprovalTemplateApproverType.SPECIFIC_USER,
                "specific_user": manager,
            }
        ],
    )

    response = employee_client.post(
        f"/api/v1/documents/{template_document.id}/submit/",
        {"approvers": [str(second_manager.id)]},
        format="json",
    )

    assert response.status_code == 200
    route = ApprovalRoute.objects.get()
    assert route.source == ApprovalRouteSource.MANUAL
    assert route.template is None
    assert route.steps.get().approver == second_manager


def test_required_unresolved_step_blocks_submit(
    employee_client, admin, template_document
):
    create_template(
        template_document.category,
        admin,
        [
            {
                "approver_type": ApprovalTemplateApproverType.DOCUMENT_RESPONSIBLE,
                "is_required": True,
            }
        ],
    )

    response = employee_client.post(
        f"/api/v1/documents/{template_document.id}/submit/", {}, format="json"
    )

    assert response.status_code == 400
    assert not ApprovalRoute.objects.exists()
    template_document.refresh_from_db()
    assert template_document.status == DocumentStatus.DRAFT


def test_inactive_specific_approver_blocks_submit(
    employee_client, admin, manager, template_document
):
    manager.is_active = False
    manager.save(update_fields=["is_active"])
    create_template(
        template_document.category,
        admin,
        [
            {
                "approver_type": ApprovalTemplateApproverType.SPECIFIC_USER,
                "specific_user": manager,
            }
        ],
    )

    response = employee_client.post(
        f"/api/v1/documents/{template_document.id}/submit/", {}, format="json"
    )

    assert response.status_code == 400
    assert not ApprovalRoute.objects.exists()


def test_same_resolved_user_cannot_appear_twice(
    employee_client, admin, manager, roles, template_document
):
    create_template(
        template_document.category,
        admin,
        [
            {
                "approver_type": ApprovalTemplateApproverType.SPECIFIC_USER,
                "specific_user": manager,
            },
            {
                "approver_type": ApprovalTemplateApproverType.ROLE,
                "role": roles["manager"],
            },
        ],
    )

    response = employee_client.post(
        f"/api/v1/documents/{template_document.id}/submit/", {}, format="json"
    )

    assert response.status_code == 400
    assert not ApprovalRoute.objects.exists()


def test_optional_unresolved_step_is_skipped_and_route_is_reordered(
    employee_client, admin, manager, template_document
):
    create_template(
        template_document.category,
        admin,
        [
            {
                "approver_type": ApprovalTemplateApproverType.DOCUMENT_RESPONSIBLE,
                "is_required": False,
            },
            {
                "approver_type": ApprovalTemplateApproverType.SPECIFIC_USER,
                "specific_user": manager,
            },
        ],
    )

    response = employee_client.post(
        f"/api/v1/documents/{template_document.id}/submit/", {}, format="json"
    )

    assert response.status_code == 200
    route = ApprovalRoute.objects.get()
    assert list(route.steps.values_list("order", flat=True)) == [1]
    assert route.template_snapshot["steps"][0]["template_order"] == 2
    assert route.template_snapshot["steps"][0]["route_order"] == 1


def test_required_file_is_checked_before_route_creation(
    employee_client, admin, manager, template_document
):
    template_document.category.requires_file = True
    template_document.category.save(update_fields=["requires_file"])
    create_template(
        template_document.category,
        admin,
        [
            {
                "approver_type": ApprovalTemplateApproverType.SPECIFIC_USER,
                "specific_user": manager,
            }
        ],
    )

    response = employee_client.post(
        f"/api/v1/documents/{template_document.id}/submit/", {}, format="json"
    )

    assert response.status_code == 400
    assert not ApprovalRoute.objects.exists()


def test_resubmit_creates_new_snapshot_without_changing_old_route(
    employee_client,
    manager_client,
    admin,
    manager,
    second_manager,
    template_document,
):
    template = create_template(
        template_document.category,
        admin,
        [
            {
                "approver_type": ApprovalTemplateApproverType.SPECIFIC_USER,
                "specific_user": manager,
            }
        ],
    )
    first_submit = employee_client.post(
        f"/api/v1/documents/{template_document.id}/submit/", {}, format="json"
    )
    assert first_submit.status_code == 200
    first_route = ApprovalRoute.objects.get()
    first_snapshot = first_route.template_snapshot.copy()
    manager_client.post(
        f"/api/v1/documents/{template_document.id}/return/",
        {"comment": "Исправить"},
        format="json",
    )
    step = template.steps.get()
    step.specific_user = second_manager
    step.save(update_fields=["specific_user"])

    response = employee_client.post(
        f"/api/v1/documents/{template_document.id}/submit/", {}, format="json"
    )

    assert response.status_code == 200
    first_route.refresh_from_db()
    routes = list(ApprovalRoute.objects.filter(document=template_document))
    newest = routes[0]
    assert len(routes) == 2
    assert first_route.template_snapshot == first_snapshot
    assert first_route.steps.get().approver == manager
    assert newest.steps.get().approver == second_manager
    assert (
        newest.template_snapshot["steps"][0]["resolved_approver_id"]
        == str(second_manager.id)
    )
