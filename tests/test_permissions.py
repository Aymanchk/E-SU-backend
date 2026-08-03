"""Тесты разграничения доступа."""

import pytest

pytestmark = pytest.mark.django_db


class TestUsersAccess:
    def test_employee_cannot_create_user(self, employee_client):
        response = employee_client.post(
            "/api/users/",
            {"email": "x@esu.kg", "first_name": "X", "last_name": "Y"},
            format="json",
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"

    def test_admin_can_create_user(self, admin_client):
        response = admin_client.post(
            "/api/users/",
            {"email": "new@esu.kg", "first_name": "Новый", "last_name": "Юзер"},
            format="json",
        )
        assert response.status_code == 201

    def test_employee_sees_limited_fields(self, employee_client, admin):
        response = employee_client.get("/api/users/")
        assert response.status_code == 200
        results = response.json()["data"]["results"]
        if results:
            assert "status" not in results[0]
            assert "role" not in results[0]

    def test_admin_sees_full_fields(self, admin_client, employee):
        response = admin_client.get("/api/users/")
        results = response.json()["data"]["results"]
        assert "status" in results[0]
        assert "role" in results[0]

    def test_manager_sees_only_own_department(
        self, manager_client, user_factory, root_department, child_department
    ):
        user_factory(email="same@esu.kg", department=child_department)
        user_factory(email="other@esu.kg", department=root_department)

        response = manager_client.get("/api/users/")
        emails = [u["email"] for u in response.json()["data"]["results"]]
        assert "same@esu.kg" in emails
        assert "other@esu.kg" not in emails


class TestAuditAccess:
    def test_employee_denied(self, employee_client):
        assert employee_client.get("/api/audit/").status_code == 403

    def test_admin_allowed(self, admin_client):
        assert admin_client.get("/api/audit/").status_code == 200

    def test_audit_is_read_only(self, admin_client, admin):
        response = admin_client.get("/api/audit/")
        results = response.json()["data"]["results"]
        assert results
        log_id = results[0]["id"]

        patch = admin_client.patch(f"/api/audit/{log_id}/", {}, format="json")
        assert patch.status_code == 405

        delete = admin_client.delete(f"/api/audit/{log_id}/")
        assert delete.status_code == 405


class TestSettingsAccess:
    def test_employee_sees_only_public(self, employee_client):
        response = employee_client.get("/api/settings/")
        assert response.status_code == 200
        assert all(item["is_public"] for item in response.json()["data"])

    def test_employee_cannot_update(self, employee_client):
        response = employee_client.patch("/api/settings/", {"max_file_size_mb": 100}, format="json")
        assert response.status_code == 403

    def test_admin_can_update(self, admin_client):
        response = admin_client.patch("/api/settings/", {"max_file_size_mb": 100}, format="json")
        assert response.status_code == 200


class TestUnauthenticated:
    @pytest.mark.parametrize(
        "url",
        [
            "/api/users/",
            "/api/roles/",
            "/api/departments/",
            "/api/audit/",
            "/api/settings/",
            "/api/auth/me/",
        ],
    )
    def test_requires_authentication(self, api, url):
        assert api.get(url).status_code == 401

    def test_health_is_public(self, api):
        assert api.get("/api/health/").status_code == 200
