"""API журнала аудита. Только чтение."""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.permissions import HasPermission

from .constants import AuditAction
from .filters import AuditLogFilter
from .models import AuditLog
from .serializers import AuditLogSerializer


@extend_schema_view(
    list=extend_schema(summary="Журнал аудита", tags=["Audit"]),
    retrieve=extend_schema(summary="Запись журнала", tags=["Audit"]),
)
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ReadOnlyModelViewSet даёт только list и retrieve.
    Создание, изменение и удаление через API невозможны по определению.
    """

    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "audit.view"
    filterset_class = AuditLogFilter
    search_fields = ["description", "object_type", "user__email"]
    ordering_fields = ["created_at", "action"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return AuditLog.objects.select_related("user")

    @extend_schema(
        summary="Справочник действий",
        description="Список кодов действий для фильтров в интерфейсе.",
        tags=["Audit"],
    )
    @action(detail=False, methods=["get"], url_path="actions", pagination_class=None)
    def actions_list(self, request):
        return Response([{"code": code, "name": label} for code, label in AuditAction.choices])
