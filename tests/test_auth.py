"""Тесты авторизации."""

import pytest

from apps.accounts.models import UserStatus
from apps.audit.constants import AuditAction
from apps.audit.models import AuditLog

pytestmark = pytest.mark.django_db

PASSWORD = "TestPass123!"


class TestLogin:
    def test_success(self, api, employee):
        response = api.post(
            "/api/auth/login/",
            {"email": employee.email, "password": PASSWORD},
            format="json",
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "access" in data
        assert "refresh" in data
        assert data["user"]["email"] == employee.email

    def test_email_case_insensitive(self, api, employee):
        response = api.post(
            "/api/auth/login/",
            {"email": employee.email.upper(), "password": PASSWORD},
            format="json",
        )
        assert response.status_code == 200

    def test_wrong_password(self, api, employee):
        response = api.post(
            "/api/auth/login/",
            {"email": employee.email, "password": "wrong"},
            format="json",
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "validation_error"

    def test_unknown_email(self, api, db):
        response = api.post(
            "/api/auth/login/",
            {"email": "nobody@esu.kg", "password": PASSWORD},
            format="json",
        )
        assert response.status_code == 400

    def test_blocked_user_cannot_login(self, api, employee):
        employee.block()
        response = api.post(
            "/api/auth/login/",
            {"email": employee.email, "password": PASSWORD},
            format="json",
        )
        assert response.status_code == 400
        assert "заблокирована" in response.json()["error"]["message"].lower()

    def test_dismissed_user_cannot_login(self, api, employee):
        employee.status = UserStatus.DISMISSED
        employee.save()
        response = api.post(
            "/api/auth/login/",
            {"email": employee.email, "password": PASSWORD},
            format="json",
        )
        assert response.status_code == 400

    def test_deleted_user_cannot_login(self, api, employee):
        employee.delete()
        response = api.post(
            "/api/auth/login/",
            {"email": employee.email, "password": PASSWORD},
            format="json",
        )
        assert response.status_code == 400

    def test_login_is_logged(self, api, employee):
        api.post(
            "/api/auth/login/",
            {"email": employee.email, "password": PASSWORD},
            format="json",
        )
        assert AuditLog.objects.filter(user=employee, action=AuditAction.LOGIN).exists()

    def test_failed_login_is_logged(self, api, employee):
        api.post(
            "/api/auth/login/",
            {"email": employee.email, "password": "wrong"},
            format="json",
        )
        assert AuditLog.objects.filter(action=AuditAction.LOGIN_FAILED).exists()


class TestRefresh:
    def test_refresh_returns_new_access(self, api, employee):
        login = api.post(
            "/api/auth/login/",
            {"email": employee.email, "password": PASSWORD},
            format="json",
        )
        refresh = login.json()["data"]["refresh"]

        response = api.post("/api/auth/refresh/", {"refresh": refresh}, format="json")
        assert response.status_code == 200
        assert "access" in response.json()["data"]

    def test_old_refresh_blacklisted_after_rotation(self, api, employee):
        login = api.post(
            "/api/auth/login/",
            {"email": employee.email, "password": PASSWORD},
            format="json",
        )
        old_refresh = login.json()["data"]["refresh"]

        first = api.post("/api/auth/refresh/", {"refresh": old_refresh}, format="json")
        assert first.status_code == 200

        second = api.post("/api/auth/refresh/", {"refresh": old_refresh}, format="json")
        assert second.status_code == 401


class TestLogout:
    def test_logout_blacklists_refresh(self, api, employee, auth_client):
        login = api.post(
            "/api/auth/login/",
            {"email": employee.email, "password": PASSWORD},
            format="json",
        )
        access = login.json()["data"]["access"]
        refresh = login.json()["data"]["refresh"]

        api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = api.post("/api/auth/logout/", {"refresh": refresh}, format="json")
        assert response.status_code == 204

        api.credentials()
        retry = api.post("/api/auth/refresh/", {"refresh": refresh}, format="json")
        assert retry.status_code == 401

    def test_logout_requires_auth(self, api):
        response = api.post("/api/auth/logout/", {"refresh": "x"}, format="json")
        assert response.status_code == 401


class TestMe:
    def test_requires_auth(self, api):
        assert api.get("/api/auth/me/").status_code == 401

    def test_returns_profile_with_permissions(self, employee_client, employee):
        response = employee_client.get("/api/auth/me/")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["email"] == employee.email
        assert data["role"]["code"] == "employee"
        assert "documents.view" in data["permissions"]
        assert "users.manage" not in data["permissions"]
        assert data["available_actions"]["can_manage_users"] is False

    def test_admin_has_all_permissions(self, admin_client):
        response = admin_client.get("/api/auth/me/")
        permissions = response.json()["data"]["permissions"]
        assert "users.manage" in permissions
        assert "audit.view" in permissions
        assert "settings.manage" in permissions

    def test_patch_updates_own_profile(self, employee_client):
        response = employee_client.patch("/api/auth/me/", {"first_name": "Новое"}, format="json")
        assert response.status_code == 200
        assert response.json()["data"]["first_name"] == "Новое"

    def test_patch_cannot_change_role(self, employee_client, roles):
        response = employee_client.patch(
            "/api/auth/me/", {"role": str(roles["admin"].id)}, format="json"
        )
        assert response.status_code == 200
        assert response.json()["data"]["role"]["code"] == "employee"


class TestChangePassword:
    def test_success(self, employee_client, employee):
        response = employee_client.post(
            "/api/auth/change-password/",
            {
                "old_password": PASSWORD,
                "new_password": "BrandNewPass456!",
                "new_password_confirm": "BrandNewPass456!",
            },
            format="json",
        )
        assert response.status_code == 200
        employee.refresh_from_db()
        assert employee.check_password("BrandNewPass456!")

    def test_wrong_old_password(self, employee_client):
        response = employee_client.post(
            "/api/auth/change-password/",
            {
                "old_password": "wrong",
                "new_password": "BrandNewPass456!",
                "new_password_confirm": "BrandNewPass456!",
            },
            format="json",
        )
        assert response.status_code == 400
        assert "old_password" in response.json()["error"]["details"]

    def test_passwords_do_not_match(self, employee_client):
        response = employee_client.post(
            "/api/auth/change-password/",
            {
                "old_password": PASSWORD,
                "new_password": "BrandNewPass456!",
                "new_password_confirm": "Different789!",
            },
            format="json",
        )
        assert response.status_code == 400

    def test_weak_password_rejected(self, employee_client):
        response = employee_client.post(
            "/api/auth/change-password/",
            {
                "old_password": PASSWORD,
                "new_password": "12345678",
                "new_password_confirm": "12345678",
            },
            format="json",
        )
        assert response.status_code == 400


class TestPasswordReset:
    def test_forgot_password_always_same_response(self, api, employee):
        existing = api.post("/api/auth/forgot-password/", {"email": employee.email}, format="json")
        missing = api.post("/api/auth/forgot-password/", {"email": "nobody@esu.kg"}, format="json")
        assert existing.status_code == missing.status_code == 200
        assert existing.json()["data"] == missing.json()["data"]

    def test_reset_with_valid_token(self, api, employee):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid = urlsafe_base64_encode(force_bytes(employee.pk))
        token = default_token_generator.make_token(employee)

        response = api.post(
            "/api/auth/reset-password/",
            {
                "uid": uid,
                "token": token,
                "new_password": "ResetPass789!",
                "new_password_confirm": "ResetPass789!",
            },
            format="json",
        )
        assert response.status_code == 200
        employee.refresh_from_db()
        assert employee.check_password("ResetPass789!")

    def test_token_cannot_be_reused(self, api, employee):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid = urlsafe_base64_encode(force_bytes(employee.pk))
        token = default_token_generator.make_token(employee)
        payload = {
            "uid": uid,
            "token": token,
            "new_password": "ResetPass789!",
            "new_password_confirm": "ResetPass789!",
        }

        assert api.post("/api/auth/reset-password/", payload, format="json").status_code == 200
        assert api.post("/api/auth/reset-password/", payload, format="json").status_code == 400

    def test_invalid_token(self, api, employee):
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid = urlsafe_base64_encode(force_bytes(employee.pk))
        response = api.post(
            "/api/auth/reset-password/",
            {
                "uid": uid,
                "token": "неверный-токен",
                "new_password": "ResetPass789!",
                "new_password_confirm": "ResetPass789!",
            },
            format="json",
        )
        assert response.status_code == 400
