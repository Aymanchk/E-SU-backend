import pytest

from apps.documents.models import (
    ApprovalRouteTemplate,
    ApprovalTemplateApproverType,
    ApprovalTemplateDepartmentRelation,
    Document,
    DocumentCategory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def template_category(admin, child_department):
    category = DocumentCategory.objects.create(
        name="Приказы с маршрутом",
        code="template-orders",
        retention_period_days=730,
        requires_file=True,
        created_by=admin,
        updated_by=admin,
    )
    category.allowed_departments.add(child_department)
    return category


def template_payload(category, manager, manager_role, **overrides):
    payload = {
        "category": str(category.id),
        "name": "Основной маршрут",
        "is_active": True,
        "steps": [
            {
                "order": 1,
                "approver_type": ApprovalTemplateApproverType.DEPARTMENT_MANAGER,
                "is_required": True,
            },
            {
                "order": 2,
                "approver_type": ApprovalTemplateApproverType.ROLE,
                "role": str(manager_role.id),
                "is_required": True,
            },
            {
                "order": 3,
                "approver_type": ApprovalTemplateApproverType.SPECIFIC_USER,
                "specific_user": str(manager.id),
                "is_required": True,
            },
            {
                "order": 4,
                "approver_type": ApprovalTemplateApproverType.DOCUMENT_RESPONSIBLE,
                "is_required": False,
            },
        ],
    }
    payload.update(overrides)
    return payload


class TestApprovalRouteTemplateApi:
    def test_admin_creates_sequential_template(
        self, admin_client, admin, manager, roles, template_category
    ):
        response = admin_client.post(
            "/api/v1/approval-route-templates/",
            template_payload(template_category, manager, roles["manager"]),
            format="json",
        )

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["created_by"] == str(admin.id)
        assert [step["order"] for step in data["steps"]] == [1, 2, 3, 4]
        assert (
            data["steps"][0]["department_relation"]
            == ApprovalTemplateDepartmentRelation.DOCUMENT_DEPARTMENT
        )
        assert ApprovalRouteTemplate.objects.get().steps.count() == 4

    def test_only_one_active_template_per_category(
        self, admin_client, manager, roles, template_category
    ):
        payload = template_payload(template_category, manager, roles["manager"])
        assert admin_client.post(
            "/api/v1/approval-route-templates/", payload, format="json"
        ).status_code == 201

        payload["name"] = "Второй маршрут"
        response = admin_client.post(
            "/api/v1/approval-route-templates/", payload, format="json"
        )

        assert response.status_code == 400
        assert ApprovalRouteTemplate.objects.count() == 1

    def test_duplicate_step_order_is_rejected(
        self, admin_client, manager, roles, template_category
    ):
        payload = template_payload(template_category, manager, roles["manager"])
        payload["steps"][1]["order"] = 1

        response = admin_client.post(
            "/api/v1/approval-route-templates/", payload, format="json"
        )

        assert response.status_code == 400
        assert not ApprovalRouteTemplate.objects.exists()

    def test_approver_type_parameters_are_validated(
        self, admin_client, manager, roles, template_category
    ):
        payload = template_payload(template_category, manager, roles["manager"])
        payload["steps"] = [
            {
                "order": 1,
                "approver_type": ApprovalTemplateApproverType.SPECIFIC_USER,
                "role": str(roles["manager"].id),
            }
        ]

        response = admin_client.post(
            "/api/v1/approval-route-templates/", payload, format="json"
        )

        assert response.status_code == 400
        assert not ApprovalRouteTemplate.objects.exists()

    def test_patch_replaces_steps_atomically(
        self, admin_client, manager, roles, template_category
    ):
        created = admin_client.post(
            "/api/v1/approval-route-templates/",
            template_payload(template_category, manager, roles["manager"]),
            format="json",
        ).json()["data"]

        response = admin_client.patch(
            f"/api/v1/approval-route-templates/{created['id']}/",
            {
                "steps": [
                    {
                        "order": 1,
                        "approver_type": ApprovalTemplateApproverType.SPECIFIC_USER,
                        "specific_user": str(manager.id),
                    }
                ]
            },
            format="json",
        )

        assert response.status_code == 200
        assert len(response.json()["data"]["steps"]) == 1
        assert ApprovalRouteTemplate.objects.get().steps.count() == 1

    def test_employee_cannot_manage_templates(
        self, employee_client, manager, roles, template_category
    ):
        response = employee_client.post(
            "/api/v1/approval-route-templates/",
            template_payload(template_category, manager, roles["manager"]),
            format="json",
        )

        assert response.status_code == 403


def test_category_exposes_file_requirement_count_and_active_template(
    admin_client,
    admin,
    employee,
    manager,
    roles,
    child_department,
    template_category,
):
    admin_client.post(
        "/api/v1/approval-route-templates/",
        template_payload(template_category, manager, roles["manager"]),
        format="json",
    )
    Document.objects.create(
        title="Документ категории",
        document_type="order",
        category=template_category,
        author=employee,
        department=child_department,
    )

    response = admin_client.get(
        f"/api/v1/document-categories/{template_category.id}/"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["requires_file"] is True
    assert data["document_count"] == 1
    assert data["approval_route_template"]["name"] == "Основной маршрут"
