"""Тесты разграничения доступа."""

import pytest

pytestmark = pytest.mark.django_db


class TestUsersAccess:
    def test_employee_cannot_create_user(self, employee_client):
        response = employee_client.post(
            "/api/v1/users/",
            {"email": "x@esu.kg", "first_name": "X", "last_name": "Y"},
            format="json",
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"

    def test_admin_can_create_user(self, admin_client):
        response = admin_client.post(
            "/api/v1/users/",
            {"email": "new@esu.kg", "first_name": "Новый", "last_name": "Юзер"},
            format="json",
        )
        assert response.status_code == 201

    def test_employee_sees_limited_fields(self, employee_client, admin):
        response = employee_client.get("/api/v1/users/")
        assert response.status_code == 200
        results = response.json()["data"]["results"]
        if results:
            assert "status" not in results[0]
            assert "role" not in results[0]

    def test_admin_sees_full_fields(self, admin_client, employee):
        response = admin_client.get("/api/v1/users/")
        results = response.json()["data"]["results"]
        assert "status" in results[0]
        assert "role" in results[0]

    def test_manager_sees_only_own_department(
        self, manager_client, user_factory, root_department, child_department
    ):
        user_factory(email="same@esu.kg", department=child_department)
        user_factory(email="other@esu.kg", department=root_department)

        response = manager_client.get("/api/v1/users/")
        emails = [u["email"] for u in response.json()["data"]["results"]]
        assert "same@esu.kg" in emails
        assert "other@esu.kg" not in emails


class TestAuditAccess:
    def test_employee_denied(self, employee_client):
        assert employee_client.get("/api/v1/audit/").status_code == 403

    def test_admin_allowed(self, admin_client):
        assert admin_client.get("/api/v1/audit/").status_code == 200

    def test_audit_is_read_only(self, admin_client, admin):
        response = admin_client.get("/api/v1/audit/")
        results = response.json()["data"]["results"]
        assert results
        log_id = results[0]["id"]

        patch = admin_client.patch(f"/api/v1/audit/{log_id}/", {}, format="json")
        assert patch.status_code == 405

        delete = admin_client.delete(f"/api/v1/audit/{log_id}/")
        assert delete.status_code == 405


class TestSettingsAccess:
    def test_employee_sees_only_public(self, employee_client):
        response = employee_client.get("/api/v1/settings/")
        assert response.status_code == 200
        assert all(item["is_public"] for item in response.json()["data"])

    def test_employee_cannot_update(self, employee_client):
        response = employee_client.patch(
            "/api/v1/settings/", {"max_file_size_mb": 100}, format="json"
        )
        assert response.status_code == 403

    def test_admin_can_update(self, admin_client):
        response = admin_client.patch("/api/v1/settings/", {"max_file_size_mb": 100}, format="json")
        assert response.status_code == 200

    def test_update_invalidates_cache(self, admin_client):
        # Прогреваем кеш, затем меняем значение — GET должен отдать новое.
        admin_client.get("/api/v1/settings/")
        admin_client.patch("/api/v1/settings/", {"max_file_size_mb": 77}, format="json")
        response = admin_client.get("/api/v1/settings/")
        setting = next(
            item for item in response.json()["data"] if item["key"] == "max_file_size_mb"
        )
        assert setting["typed_value"] == 77


class TestUnauthenticated:
    @pytest.mark.parametrize(
        "url",
        [
            "/api/v1/users/",
            "/api/v1/roles/",
            "/api/v1/departments/",
            "/api/v1/audit/",
            "/api/v1/settings/",
            "/api/v1/auth/me/",
        ],
    )
    def test_requires_authentication(self, api, url):
        assert api.get(url).status_code == 401

    def test_health_is_public(self, api):
        assert api.get("/api/health/").status_code == 200
