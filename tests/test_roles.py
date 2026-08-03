"""Тесты ролей и прав."""

import pytest

from apps.accounts.models import Permission, Role

pytestmark = pytest.mark.django_db


def test_seed_created_roles_and_permissions(db):
    assert Permission.objects.count() == 12
    codes = set(Role.objects.values_list("code", flat=True))
    assert {"admin", "employee", "manager", "office"}.issubset(codes)
    assert Role.objects.get(code="admin").permissions.filter(code="documents.register").exists()
    assert Role.objects.get(code="office").permissions.filter(code="documents.register").exists()


def test_system_roles_cannot_be_deleted(admin_client, roles):
    response = admin_client.delete(f"/api/roles/{roles['employee'].id}/")
    assert response.status_code == 400


def test_create_custom_role(admin_client):
    response = admin_client.post(
        "/api/roles/",
        {
            "code": "archivist",
            "name": "Архивариус",
            "permissions": ["documents.view", "documents.archive"],
        },
        format="json",
    )
    assert response.status_code == 201
    role = Role.objects.get(code="archivist")
    assert set(role.permission_codes) == {"documents.view", "documents.archive"}


def test_set_permissions_replaces_set(admin_client, roles):
    role = roles["employee"]
    response = admin_client.put(
        f"/api/roles/{role.id}/permissions/",
        {"permissions": ["documents.view"]},
        format="json",
    )
    assert response.status_code == 200
    role.refresh_from_db()
    assert role.permission_codes == ["documents.view"]


def test_unknown_permission_rejected(admin_client, roles):
    response = admin_client.put(
        f"/api/roles/{roles['employee'].id}/permissions/",
        {"permissions": ["documents.view", "не.существует"]},
        format="json",
    )
    assert response.status_code == 400


def test_permissions_list(admin_client):
    response = admin_client.get("/api/permissions/")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 12
