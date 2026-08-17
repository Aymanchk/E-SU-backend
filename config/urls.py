from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.common.views import HealthView

# Основные эндпоинты приложений. Подключаются под версионированным префиксом
# /api/v1/ (канонический) и под старым /api/ ради обратной совместимости.
# Views и serializers не дублируются — переиспользуются одни и те же URL-модули.
api_patterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("auth/", include("apps.accounts.urls_auth")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.organizations.urls")),
    path("", include("apps.audit.urls")),
    path("", include("apps.common.urls")),
    path("", include("apps.documents.urls")),
    path("", include("apps.notifications.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    # Служебные (вне версионирования)
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    # Версионированный API (канонический)
    path(f"api/{settings.API_VERSION}/", include((api_patterns, settings.API_VERSION))),
    # Legacy-префикс, обратная совместимость (deprecated)
    path("api/", include((api_patterns, "legacy"))),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
