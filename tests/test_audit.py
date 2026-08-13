"""Тесты журнала аудита."""

import pytest

from apps.audit.constants import AuditAction
from apps.audit.models import AuditLog

pytestmark = pytest.mark.django_db


def test_user_creation_is_logged(admin_client):
    admin_client.post(
        "/api/v1/users/",
        {"email": "logged@esu.kg", "first_name": "A", "last_name": "B"},
        format="json",
    )
    assert AuditLog.objects.filter(action=AuditAction.USER_CREATE).exists()


def test_block_is_logged(admin_client, employee):
    admin_client.post(f"/api/v1/users/{employee.id}/block/")
    log = AuditLog.objects.filter(action=AuditAction.USER_BLOCK).first()
    assert log is not None
    assert log.object_id == str(employee.id)


def test_department_creation_is_logged(admin_client):
    admin_client.post("/api/v1/departments/", {"name": "Новый", "code": "new"}, format="json")
    assert AuditLog.objects.filter(action=AuditAction.DEPARTMENT_CREATE).exists()


def test_role_permissions_change_is_logged(admin_client, roles):
    admin_client.put(
        f"/api/v1/roles/{roles['employee'].id}/permissions/",
        {"permissions": ["documents.view"]},
        format="json",
    )
    log = AuditLog.objects.filter(action=AuditAction.ROLE_PERMISSIONS_UPDATE).first()
    assert log is not None
    assert "removed" in log.metadata


def test_log_stores_ip_and_user_agent(api, employee):
    api.post(
        "/api/v1/auth/login/",
        {"email": employee.email, "password": "TestPass123!"},
        format="json",
        HTTP_USER_AGENT="pytest-agent",
    )
    log = AuditLog.objects.filter(action=AuditAction.LOGIN).first()
    assert log.ip_address is not None
    assert "pytest" in log.user_agent


def test_audit_filters(admin_client, employee):
    admin_client.post(f"/api/v1/users/{employee.id}/block/")

    response = admin_client.get(f"/api/v1/audit/?action={AuditAction.USER_BLOCK}")
    assert response.status_code == 200
    assert response.json()["data"]["count"] >= 1

    empty = admin_client.get("/api/v1/audit/?action=role_delete")
    assert empty.json()["data"]["count"] == 0


def test_log_record_cannot_be_modified(db, admin):
    log = AuditLog.objects.create(action=AuditAction.LOGIN, user=admin)
    log.description = "изменено"
    with pytest.raises(ValueError):
        log.save()

    with pytest.raises(ValueError):
        log.delete()
