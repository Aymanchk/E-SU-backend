"""Служебные эндпоинты."""

import redis
from django.conf import settings
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.constants import AuditAction
from apps.audit.services import log_action

from .models import SystemSetting
from .serializers import SystemSettingSerializer, SystemSettingsUpdateSerializer
from .settings_service import get_all_settings_data, invalidate_settings_cache


class HealthView(APIView):
    """Проверка работоспособности сервиса."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Health-check",
        description="Проверяет приложение, базу данных и Redis.",
        tags=["System"],
        responses={200: dict, 503: dict},
    )
    def get(self, request):
        checks = {
            "application": True,
            "database": self._check_database(),
            "redis": self._check_redis(),
        }

        all_ok = all(checks.values())
        return Response(
            {
                "status": "ok" if all_ok else "degraded",
                "checks": checks,
                "version": settings.SPECTACULAR_SETTINGS["VERSION"],
            },
            status=status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    @staticmethod
    def _check_database():
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return True
        except Exception:
            return False

    @staticmethod
    def _check_redis():
        broker_url = getattr(settings, "CELERY_BROKER_URL", "")
        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False) or not broker_url or not broker_url.startswith("redis"):
            return True
        try:
            client = redis.Redis.from_url(broker_url, socket_timeout=2)
            return bool(client.ping())
        except Exception:
            return False


class SystemSettingsView(APIView):
    """
    GET  /api/settings/    список настроек
    PATCH /api/settings/   обновление нескольких настроек сразу
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Системные настройки",
        description=("Пользователь без права settings.manage видит только публичные настройки."),
        tags=["Settings"],
        responses={200: SystemSettingSerializer(many=True)},
    )
    def get(self, request):
        # Настройки кешируются; приватные скрываем от пользователей без прав.
        data = get_all_settings_data()

        if not request.user.has_permission("settings.manage"):
            data = [item for item in data if item["is_public"]]

        return Response(data)

    @extend_schema(
        summary="Изменение системных настроек",
        description='Принимает объект вида {"max_file_size_mb": 50}.',
        tags=["Settings"],
        request=SystemSettingsUpdateSerializer,
        responses={200: SystemSettingSerializer(many=True)},
    )
    def patch(self, request):
        if not request.user.has_permission("settings.manage"):
            raise PermissionDenied("Недостаточно прав для изменения настроек")

        serializer = SystemSettingsUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        changes = {}
        settings_map = {s.key: s for s in SystemSetting.objects.filter(key__in=payload.keys())}

        for key, raw_value in payload.items():
            setting = settings_map[key]
            old_value = setting.value
            setting.set_value(raw_value)
            setting.updated_by = request.user
            setting.save(update_fields=["value", "updated_by", "updated_at"])
            if old_value != setting.value:
                changes[key] = [old_value, setting.value]

        if changes:
            log_action(
                request,
                action=AuditAction.SETTINGS_UPDATE,
                description=f"Изменены настройки: {', '.join(changes.keys())}",
                metadata={"changes": changes},
            )
            # Инвалидируем кеш, чтобы GET сразу отдал новые значения.
            invalidate_settings_cache()

        return Response(get_all_settings_data())
