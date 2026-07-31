from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.permissions import HasPermissionPerAction

from .filters import DocumentCategoryFilter
from .models import DocumentCategory
from .serializers import DocumentCategorySerializer
from .services import DocumentCategoryService


@extend_schema_view(
    list=extend_schema(summary="Список категорий документов", tags=["Document categories"]),
    retrieve=extend_schema(summary="Категория документов", tags=["Document categories"]),
    create=extend_schema(summary="Создать категорию", tags=["Document categories"]),
    partial_update=extend_schema(summary="Изменить категорию", tags=["Document categories"]),
    destroy=extend_schema(summary="Удалить категорию", tags=["Document categories"]),
)
class DocumentCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentCategorySerializer
    permission_classes = [IsAuthenticated, HasPermissionPerAction]
    permission_map = {
        "list": None,
        "retrieve": None,
        "create": "categories.manage",
        "update": "categories.manage",
        "partial_update": "categories.manage",
        "destroy": "categories.manage",
        "activate": "categories.manage",
        "deactivate": "categories.manage",
    }
    filterset_class = DocumentCategoryFilter
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "code", "status", "created_at"]
    ordering = ["name"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return DocumentCategory.objects.select_related("created_by").prefetch_related(
            "allowed_departments"
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        DocumentCategoryService.delete(instance)

    @extend_schema(summary="Активировать категорию", tags=["Document categories"])
    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        category = DocumentCategoryService.activate(self.get_object(), request.user)
        return Response(self.get_serializer(category).data)

    @extend_schema(summary="Деактивировать категорию", tags=["Document categories"])
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        category = DocumentCategoryService.deactivate(self.get_object(), request.user)
        return Response(self.get_serializer(category).data)
