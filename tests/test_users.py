"""Тесты API пользователей."""

import pytest

from apps.accounts.models import User, UserStatus

pytestmark = pytest.mark.django_db


class TestUserCrud:
    def test_create_generates_password_and_hides_it(self, admin_client):
        response = admin_client.post(
            "/api/v1/users/",
            {
                "email": "created@esu.kg",
                "first_name": "Создан",
                "last_name": "Пользователь",
                "position": "Специалист",
            },
            format="json",
        )
        assert response.status_code == 201
        assert "password" not in response.json()["data"]

        user = User.objects.get(email="created@esu.kg")
        assert user.status == UserStatus.INVITED
        assert user.password.startswith(("argon2", "pbkdf2"))

    def test_duplicate_email_rejected(self, admin_client, employee):
        response = admin_client.post(
            "/api/v1/users/",
            {"email": employee.email, "first_name": "A", "last_name": "B"},
            format="json",
        )
        assert response.status_code == 400
        assert "email" in response.json()["error"]["details"]

    def test_update(self, admin_client, employee):
        response = admin_client.patch(
            f"/api/v1/users/{employee.id}/", {"position": "Ведущий"}, format="json"
        )
        assert response.status_code == 200
        employee.refresh_from_db()
        assert employee.position == "Ведущий"

    def test_soft_delete(self, admin_client, employee):
        response = admin_client.delete(f"/api/v1/users/{employee.id}/")
        assert response.status_code == 204

        assert not User.objects.filter(id=employee.id).exists()
        assert User.all_objects.filter(id=employee.id).exists()

        deleted = User.all_objects.get(id=employee.id)
        assert deleted.is_deleted is True
        assert deleted.deleted_at is not None

    def test_cannot_delete_self(self, admin_client, admin):
        response = admin_client.delete(f"/api/v1/users/{admin.id}/")
        assert response.status_code == 400


class TestUserActions:
    def test_block(self, admin_client, employee):
        response = admin_client.post(f"/api/v1/users/{employee.id}/block/")
        assert response.status_code == 200
        employee.refresh_from_db()
        assert employee.status == UserStatus.BLOCKED
        assert employee.is_active is False

    def test_cannot_block_self(self, admin_client, admin):
        assert admin_client.post(f"/api/v1/users/{admin.id}/block/").status_code == 400

    def test_activate(self, admin_client, employee):
        employee.block()
        response = admin_client.post(f"/api/v1/users/{employee.id}/activate/")
        assert response.status_code == 200
        employee.refresh_from_db()
        assert employee.status == UserStatus.ACTIVE
        assert employee.is_active is True

    def test_reset_password(self, admin_client, employee):
        old_hash = employee.password
        response = admin_client.post(f"/api/v1/users/{employee.id}/reset-password/")
        assert response.status_code == 200
        employee.refresh_from_db()
        assert employee.password != old_hash


class TestUserFilters:
    def test_search_by_name(self, admin_client, user_factory):
        user_factory(email="ivanov@esu.kg", last_name="Иванов")
        user_factory(email="petrov@esu.kg", last_name="Петров")

        response = admin_client.get("/api/v1/users/?search=Иванов")
        emails = [u["email"] for u in response.json()["data"]["results"]]
        assert "ivanov@esu.kg" in emails
        assert "petrov@esu.kg" not in emails

    def test_filter_by_role(self, admin_client, employee, manager):
        response = admin_client.get("/api/v1/users/?role=manager")
        emails = [u["email"] for u in response.json()["data"]["results"]]
        assert manager.email in emails
        assert employee.email not in emails

    def test_filter_by_status(self, admin_client, employee):
        employee.block()
        response = admin_client.get("/api/v1/users/?status=blocked")
        emails = [u["email"] for u in response.json()["data"]["results"]]
        assert employee.email in emails

    def test_filter_by_department(self, admin_client, employee, child_department):
        response = admin_client.get(f"/api/v1/users/?department={child_department.id}")
        emails = [u["email"] for u in response.json()["data"]["results"]]
        assert employee.email in emails

    def test_pagination_format(self, admin_client):
        response = admin_client.get("/api/v1/users/?page_size=1")
        data = response.json()["data"]
        assert {"count", "next", "previous", "results"}.issubset(data.keys())
        assert len(data["results"]) <= 1
