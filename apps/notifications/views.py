from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer
from .services import NotificationService


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["type", "is_read", "document"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return Notification.objects.filter(recipient=self.request.user).select_related("document")

    @extend_schema(summary="Количество непрочитанных уведомлений", tags=["Notifications"])
    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        return Response({"count": self.get_queryset().filter(is_read=False).count()})

    @extend_schema(summary="Отметить уведомление прочитанным", tags=["Notifications"])
    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = NotificationService.mark_read(self.get_object())
        return Response(self.get_serializer(notification).data)

    @extend_schema(summary="Отметить все уведомления прочитанными", tags=["Notifications"])
    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        updated = NotificationService.mark_all_read(request.user)
        return Response({"updated": updated}, status=status.HTTP_200_OK)
