import pytest

from apps.documents.models import DocumentCategory, DocumentCategoryStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def category(admin, child_department):
    category = DocumentCategory.objects.create(
        name="Приказы",
        code="orders",
        description="Приказы университета",
        retention_period_days=1825,
        created_by=admin,
        updated_by=admin,
    )
    category.allowed_departments.add(child_department)
    return category


class TestDocumentCategoryCrud:
    def test_admin_can_create(self, admin_client, child_department):
        response = admin_client.post(
            "/api/document-categories/",
            {
                "name": "Договоры",
                "code": "contracts",
                "description": "Договоры университета",
                "retention_period_days": 3650,
                "allowed_departments": [str(child_department.id)],
            },
            format="json",
        )

        assert response.status_code == 201
        created = DocumentCategory.objects.get(code="contracts")
        assert created.created_by_id is not None
        assert list(created.allowed_departments.values_list("id", flat=True)) == [
            child_department.id
        ]

    def test_office_can_create(self, auth_client, user_factory, child_department):
        office = user_factory(role_code="office", department=child_department)
        response = auth_client(office).post(
            "/api/document-categories/",
            {"name": "Заявления", "code": "requests", "retention_period_days": 365},
            format="json",
        )
        assert response.status_code == 201

    def test_employee_can_read_but_cannot_create(self, employee_client, category):
        assert employee_client.get("/api/document-categories/").status_code == 200
        response = employee_client.post(
            "/api/document-categories/",
            {"name": "Секретная", "code": "secret", "retention_period_days": 30},
            format="json",
        )
        assert response.status_code == 403

    def test_patch(self, admin_client, category):
        response = admin_client.patch(
            f"/api/document-categories/{category.id}/",
            {"retention_period_days": 2000},
            format="json",
        )
        assert response.status_code == 200
        category.refresh_from_db()
        assert category.retention_period_days == 2000

    def test_duplicate_code_rejected(self, admin_client, category):
        response = admin_client.post(
            "/api/document-categories/",
            {"name": "Другая", "code": category.code, "retention_period_days": 10},
            format="json",
        )
        assert response.status_code == 400

    def test_delete_is_soft(self, admin_client, category):
        response = admin_client.delete(f"/api/document-categories/{category.id}/")
        assert response.status_code == 204
        assert not DocumentCategory.objects.filter(pk=category.pk).exists()
        assert DocumentCategory.all_objects.filter(pk=category.pk, is_deleted=True).exists()

    def test_deleted_code_cannot_be_reused(self, admin_client, category):
        admin_client.delete(f"/api/document-categories/{category.id}/")
        response = admin_client.post(
            "/api/document-categories/",
            {"name": "Новая", "code": category.code, "retention_period_days": 10},
            format="json",
        )
        assert response.status_code == 400


class TestDocumentCategoryStatusActions:
    def test_deactivate_and_activate(self, admin_client, category):
        response = admin_client.post(f"/api/document-categories/{category.id}/deactivate/")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == DocumentCategoryStatus.INACTIVE

        response = admin_client.post(f"/api/document-categories/{category.id}/activate/")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == DocumentCategoryStatus.ACTIVE

    def test_employee_cannot_change_status(self, employee_client, category):
        response = employee_client.post(f"/api/document-categories/{category.id}/deactivate/")
        assert response.status_code == 403


class TestDocumentCategoryFilters:
    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("name=при", 1),
            ("code=ORDERS", 1),
            ("status=active", 1),
            ("status=inactive", 0),
        ],
    )
    def test_scalar_filters(self, employee_client, category, query, expected):
        response = employee_client.get(f"/api/document-categories/?{query}")
        assert response.status_code == 200
        assert response.json()["data"]["count"] == expected

    def test_department_filter(self, employee_client, category, child_department, root_department):
        included = employee_client.get(
            f"/api/document-categories/?department={child_department.id}"
        )
        excluded = employee_client.get(
            f"/api/document-categories/?department={root_department.id}"
        )
        assert included.json()["data"]["count"] == 1
        assert excluded.json()["data"]["count"] == 0
