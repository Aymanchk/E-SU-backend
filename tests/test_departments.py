"""Тесты подразделений."""

import pytest

from apps.organizations.models import Department

pytestmark = pytest.mark.django_db


class TestDepartmentCrud:
    def test_create(self, admin_client):
        response = admin_client.post(
            "/api/v1/departments/",
            {"name": "Учебный отдел", "code": "education"},
            format="json",
        )
        assert response.status_code == 201

    def test_employee_cannot_create(self, employee_client):
        response = employee_client.post(
            "/api/v1/departments/",
            {"name": "Отдел", "code": "dep"},
            format="json",
        )
        assert response.status_code == 403

    def test_duplicate_code_rejected(self, admin_client, root_department):
        response = admin_client.post(
            "/api/v1/departments/",
            {"name": "Другое", "code": root_department.code},
            format="json",
        )
        assert response.status_code == 400

    def test_cannot_delete_with_employees(self, admin_client, employee, child_department):
        response = admin_client.delete(f"/api/v1/departments/{child_department.id}/")
        assert response.status_code == 400
        assert "сотрудник" in response.json()["error"]["message"].lower()

    def test_cannot_delete_with_children(self, admin_client, root_department, child_department):
        response = admin_client.delete(f"/api/v1/departments/{root_department.id}/")
        assert response.status_code == 400

    def test_delete_empty_department(self, admin_client):
        department = Department.objects.create(name="Пустой", code="empty")
        response = admin_client.delete(f"/api/v1/departments/{department.id}/")
        assert response.status_code == 204
        assert not Department.objects.filter(id=department.id).exists()
        assert Department.all_objects.filter(id=department.id).exists()


class TestDepartmentTree:
    def test_tree_structure(self, admin_client, root_department, child_department):
        response = admin_client.get("/api/v1/departments/tree/")
        assert response.status_code == 200

        roots = response.json()["data"]
        assert len(roots) == 1
        assert roots[0]["code"] == root_department.code
        assert len(roots[0]["children"]) == 1
        assert roots[0]["children"][0]["code"] == child_department.code

    def test_deep_nesting(self, admin_client, root_department, child_department):
        Department.objects.create(name="Отдел разработки", code="dev", parent=child_department)
        response = admin_client.get("/api/v1/departments/tree/")
        roots = response.json()["data"]
        assert roots[0]["children"][0]["children"][0]["code"] == "dev"


class TestDepartmentEmployees:
    def test_returns_employees(self, admin_client, employee, child_department):
        response = admin_client.get(f"/api/v1/departments/{child_department.id}/employees/")
        assert response.status_code == 200
        emails = [u["email"] for u in response.json()["data"]["results"]]
        assert employee.email in emails

    def test_include_children(self, admin_client, user_factory, root_department, child_department):
        user_factory(email="child@esu.kg", department=child_department)

        without = admin_client.get(f"/api/v1/departments/{root_department.id}/employees/")
        with_children = admin_client.get(
            f"/api/v1/departments/{root_department.id}/employees/?include_children=true"
        )

        emails_without = [u["email"] for u in without.json()["data"]["results"]]
        emails_with = [u["email"] for u in with_children.json()["data"]["results"]]

        assert "child@esu.kg" not in emails_without
        assert "child@esu.kg" in emails_with


class TestCycleProtection:
    def test_cannot_set_self_as_parent(self, admin_client, root_department):
        response = admin_client.patch(
            f"/api/v1/departments/{root_department.id}/",
            {"parent": str(root_department.id)},
            format="json",
        )
        assert response.status_code == 400

    def test_cannot_set_descendant_as_parent(self, admin_client, root_department, child_department):
        response = admin_client.patch(
            f"/api/v1/departments/{root_department.id}/",
            {"parent": str(child_department.id)},
            format="json",
        )
        assert response.status_code == 400
