"""Тесты общей инфраструктуры."""

import pytest

pytestmark = pytest.mark.django_db


def test_health_check(api):
    response = api.get("/api/health/")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] in ("ok", "degraded")
    assert "database" in data["checks"]
    assert "redis" in data["checks"]


def test_success_response_format(admin_client):
    response = admin_client.get("/api/v1/auth/me/")
    assert set(response.json().keys()) == {"data", "message"}
    assert response.json()["message"] == "Success"


def test_error_response_format(api):
    response = api.get("/api/v1/auth/me/")
    assert "error" in response.json()
    assert set(response.json()["error"].keys()) == {"code", "message", "details"}


def test_not_found_format(admin_client):
    response = admin_client.get("/api/v1/users/00000000-0000-0000-0000-000000000000/")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_legacy_api_prefix_still_works(admin_client):
    """Старый /api/ префикс сохранён для обратной совместимости (ТЗ §3)."""
    legacy = admin_client.get("/api/auth/me/")
    versioned = admin_client.get("/api/v1/auth/me/")
    assert legacy.status_code == 200
    assert versioned.status_code == 200
    assert legacy.json()["data"]["email"] == versioned.json()["data"]["email"]


def test_schema_generates(admin_client):
    response = admin_client.get("/api/schema/")
    assert response.status_code == 200


def test_docs_available(admin_client):
    response = admin_client.get("/api/docs/")
    assert response.status_code == 200
