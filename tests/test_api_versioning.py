import pytest

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/document-categories/",
        "/api/v1/documents/",
        "/api/v1/notifications/",
        "/api/v1/dashboard/",
        "/api/v1/auth/me/",
    ],
)
def test_v1_endpoints_are_registered(api, path):
    response = api.get(path)

    assert response.status_code == 401


def test_v1_health_endpoint(api):
    response = api.get("/api/v1/health/")

    assert response.status_code == 200
    assert response.json()["data"]["status"] in {"ok", "degraded"}


def test_legacy_api_remains_temporarily_available(api):
    response = api.get("/api/documents/")

    assert response.status_code == 401


def test_openapi_contains_only_versioned_application_paths(admin_client):
    response = admin_client.get("/api/schema/", HTTP_ACCEPT="application/json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/documents/" in paths
    assert "/api/documents/" not in paths
    upload_content = paths["/api/v1/documents/{id}/files/"]["post"]["requestBody"][
        "content"
    ]
    assert list(upload_content) == ["multipart/form-data"]
