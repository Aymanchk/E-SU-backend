from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.permissions import HasPermissionPerAction

from .filters import DocumentCategoryFilter, DocumentFilter
from .models import Document, DocumentCategory, DocumentStatus
from .serializers import (
    DocumentCategorySerializer,
    DocumentDetailSerializer,
    DocumentListSerializer,
    DocumentWriteSerializer,
)
from .services import DocumentCategoryService, DocumentService


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


@extend_schema_view(
    list=extend_schema(summary="Список документов", tags=["Documents"]),
    retrieve=extend_schema(summary="Документ", tags=["Documents"]),
    create=extend_schema(summary="Создать документ", tags=["Documents"]),
    partial_update=extend_schema(summary="Изменить документ", tags=["Documents"]),
    destroy=extend_schema(summary="Удалить черновик", tags=["Documents"]),
)
class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.none()
    permission_classes = [IsAuthenticated, HasPermissionPerAction]
    permission_map = {
        "create": "documents.create",
        "list": "documents.view",
        "retrieve": "documents.view",
        "my": "documents.view",
        "returned": "documents.view",
        "overdue": "documents.view",
        "archive_list": "documents.view",
        "for_approval": "documents.approve",
    }
    filterset_class = DocumentFilter
    search_fields = ["title", "description", "registration_number"]
    ordering_fields = ["created_at", "deadline", "title", "priority", "status"]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = Document.objects.select_related(
            "category", "author", "department", "responsible"
        )
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        return DocumentService.visible_to(self.request.user, queryset)

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return DocumentWriteSerializer
        if self.action == "retrieve":
            return DocumentDetailSerializer
        return DocumentListSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_update(self, serializer):
        DocumentService.ensure_can_edit(self.get_object(), self.request.user)
        serializer.save()

    def perform_destroy(self, instance):
        DocumentService.ensure_can_delete(instance, self.request.user)
        instance.delete()

    def _service_response(self, document):
        return Response(DocumentDetailSerializer(document, context=self.get_serializer_context()).data)

    @extend_schema(summary="Мои документы", tags=["Documents"])
    @action(detail=False, methods=["get"])
    def my(self, request):
        return self._paginated(self.filter_queryset(self.get_queryset().filter(author=request.user)))

    @extend_schema(summary="Документы на согласование", tags=["Documents"])
    @action(detail=False, methods=["get"], url_path="for-approval")
    def for_approval(self, request):
        # Наполнение будет подключено вместе с ApprovalStep на этапе согласования.
        return self._paginated(self.get_queryset().none())

    @extend_schema(summary="Возвращённые документы", tags=["Documents"])
    @action(detail=False, methods=["get"])
    def returned(self, request):
        queryset = self.get_queryset().filter(author=request.user, status=DocumentStatus.RETURNED)
        return self._paginated(self.filter_queryset(queryset))

    @extend_schema(summary="Просроченные документы", tags=["Documents"])
    @action(detail=False, methods=["get"])
    def overdue(self, request):
        return self._paginated(
            self.filter_queryset(self.get_queryset().filter(status=DocumentStatus.OVERDUE))
        )

    @extend_schema(summary="Архив документов", tags=["Documents"])
    @action(detail=False, methods=["get"], url_path="archive")
    def archive_list(self, request):
        return self._paginated(
            self.filter_queryset(self.get_queryset().filter(status=DocumentStatus.ARCHIVED))
        )

    def _paginated(self, queryset):
        page = self.paginate_queryset(queryset)
        serializer = DocumentListSerializer(
            page if page is not None else queryset,
            many=True,
            context=self.get_serializer_context(),
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @extend_schema(summary="Отправить документ", tags=["Documents"])
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        return self._service_response(DocumentService.submit(self.get_object(), request.user))

    @extend_schema(summary="Завершить документ", tags=["Documents"])
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        return self._service_response(DocumentService.complete(self.get_object(), request.user))

    @extend_schema(summary="Архивировать документ", tags=["Documents"])
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        return self._service_response(DocumentService.archive(self.get_object(), request.user))

    @extend_schema(summary="Восстановить документ", tags=["Documents"])
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        return self._service_response(DocumentService.restore(self.get_object(), request.user))
