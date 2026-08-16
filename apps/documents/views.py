from django.db.models import Count, Q
from django.http import FileResponse
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import HasPermissionPerAction
from apps.notifications.models import NotificationType
from apps.notifications.services import NotificationService

from .access import DocumentAccessService
from .filters import DocumentCategoryFilter, DocumentFilter
from .models import (
    ApprovalRouteTemplate,
    ApprovalStep,
    ApprovalStepStatus,
    Document,
    DocumentCategory,
    DocumentComment,
    DocumentFile,
    DocumentStatus,
)
from .serializers import (
    ApprovalDecisionSerializer,
    ApprovalReturnSerializer,
    ApprovalRouteSerializer,
    ApprovalRouteTemplateSerializer,
    DashboardSerializer,
    DocumentCategorySerializer,
    DocumentCommentCreateSerializer,
    DocumentCommentSerializer,
    DocumentDetailSerializer,
    DocumentFileSerializer,
    DocumentFileUploadSerializer,
    DocumentHistorySerializer,
    DocumentListSerializer,
    DocumentSubmitSerializer,
    DocumentWriteSerializer,
)
from .services import (
    ApprovalService,
    CommentService,
    DashboardService,
    DocumentCategoryService,
    DocumentService,
    FileService,
    HistoryService,
    RegistrationService,
)


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Сводная панель документов",
        responses=DashboardSerializer,
        tags=["Dashboard"],
    )
    def get(self, request):
        data = DashboardService.build(request.user)
        return Response(DashboardSerializer(data).data)


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
        return (
            DocumentCategory.objects.select_related("created_by")
            .prefetch_related(
                "allowed_departments",
                "approval_route_templates__steps__role",
                "approval_route_templates__steps__specific_user",
            )
            .annotate(
                document_count=Count(
                    "documents",
                    filter=Q(documents__is_deleted=False),
                    distinct=True,
                )
            )
            .distinct()
        )

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
    list=extend_schema(summary="Список шаблонов маршрутов", tags=["Approval templates"]),
    retrieve=extend_schema(summary="Шаблон маршрута", tags=["Approval templates"]),
    create=extend_schema(summary="Создать шаблон маршрута", tags=["Approval templates"]),
    partial_update=extend_schema(summary="Изменить шаблон маршрута", tags=["Approval templates"]),
    destroy=extend_schema(summary="Удалить шаблон маршрута", tags=["Approval templates"]),
)
class ApprovalRouteTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = ApprovalRouteTemplateSerializer
    permission_classes = [IsAuthenticated, HasPermissionPerAction]
    permission_map = {
        "list": "categories.manage",
        "retrieve": "categories.manage",
        "create": "categories.manage",
        "update": "categories.manage",
        "partial_update": "categories.manage",
        "destroy": "categories.manage",
    }
    filterset_fields = ["category", "is_active"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["category__name", "name"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return ApprovalRouteTemplate.objects.select_related("category").prefetch_related(
            "steps__role", "steps__specific_user"
        )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


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
        "update": "documents.create",
        "partial_update": "documents.create",
        "destroy": "documents.create",
        "my": "documents.view",
        "returned": "documents.view",
        "overdue": "documents.view",
        "archive_list": "documents.view",
        "for_approval": "documents.approve",
        "register": "documents.register",
        "submit": "documents.create",
        "approval": "documents.view",
        "approve": "documents.approve",
        "return_document": "documents.return",
        "complete": ["documents.edit", "documents.create"],
        "archive": "documents.archive",
        "restore": "documents.archive",
        "files": "documents.view",
        "comments": "documents.view",
        "history": "documents.view",
    }
    filterset_class = DocumentFilter
    search_fields = ["title", "description", "registration_number"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "deadline",
        "title",
        "priority",
        "status",
        "registration_number",
    ]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = Document.objects.select_related(
            "category", "author", "department", "responsible"
        )
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        return DocumentAccessService.visible_to(self.request.user, queryset)

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return DocumentWriteSerializer
        if self.action == "retrieve":
            return DocumentDetailSerializer
        return DocumentListSerializer

    def perform_create(self, serializer):
        document = serializer.save(author=self.request.user)
        HistoryService.record(
            document,
            self.request.user,
            "created",
            new_values=HistoryService.snapshot(document),
            description="Документ создан",
        )
        if document.responsible and document.responsible_id != self.request.user.id:
            NotificationService.create(
                recipient=document.responsible,
                notification_type=NotificationType.RESPONSIBLE_ASSIGNED,
                title="Вы назначены ответственным",
                message=f"Вы назначены ответственным за документ «{document.title}».",
                document=document,
            )

    def perform_update(self, serializer):
        DocumentService.ensure_can_edit(self.get_object(), self.request.user)
        old_values = HistoryService.snapshot(serializer.instance)
        old_responsible_id = serializer.instance.responsible_id
        document = serializer.save()
        HistoryService.record(
            document,
            self.request.user,
            "updated",
            old_values=old_values,
            new_values=HistoryService.snapshot(document),
            description=f"Изменены поля: {', '.join(self.request.data.keys())}",
        )
        if (
            document.responsible
            and document.responsible_id != old_responsible_id
            and document.responsible_id != self.request.user.id
        ):
            NotificationService.create(
                recipient=document.responsible,
                notification_type=NotificationType.RESPONSIBLE_ASSIGNED,
                title="Вы назначены ответственным",
                message=f"Вы назначены ответственным за документ «{document.title}».",
                document=document,
            )

    def perform_destroy(self, instance):
        DocumentService.ensure_can_delete(instance, self.request.user)
        instance.delete()

    def _service_response(self, document):
        return Response(
            DocumentDetailSerializer(document, context=self.get_serializer_context()).data
        )

    @extend_schema(summary="Мои документы", tags=["Documents"])
    @action(detail=False, methods=["get"])
    def my(self, request):
        return self._paginated(
            self.filter_queryset(self.get_queryset().filter(author=request.user))
        )

    @extend_schema(summary="Документы на согласование", tags=["Documents"])
    @action(detail=False, methods=["get"], url_path="for-approval")
    def for_approval(self, request):
        current_steps = ApprovalStep.objects.filter(status=ApprovalStepStatus.CURRENT)
        if not request.user.is_admin_role:
            current_steps = current_steps.filter(approver=request.user)
        queryset = self.get_queryset().filter(pk__in=current_steps.values("document_id"))
        return self._paginated(self.filter_queryset(queryset.distinct()))

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

    @extend_schema(
        summary="Отправить документ на согласование",
        tags=["Documents"],
        request=DocumentSubmitSerializer,
        responses={200: ApprovalRouteSerializer},
    )
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        document = self.get_object()
        serializer = DocumentSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        route = ApprovalService.submit(
            document, request.user, serializer.validated_data["approvers"]
        )
        return Response(ApprovalRouteSerializer(route).data)

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

    @extend_schema(summary="Зарегистрировать документ", tags=["Documents"])
    @action(detail=True, methods=["post"])
    def register(self, request, pk=None):
        document = RegistrationService.register(self.get_object(), request.user)
        return self._service_response(document)

    @extend_schema(
        summary="Маршрут согласования документа",
        tags=["Approvals"],
        responses={200: ApprovalRouteSerializer},
    )
    @action(detail=True, methods=["get"])
    def approval(self, request, pk=None):
        document = self.get_object()
        route = (
            document.approval_routes.prefetch_related("steps__approver", "steps__role")
            .select_related("created_by")
            .first()
        )
        if route is None:
            from rest_framework.exceptions import NotFound

            raise NotFound("Маршрут согласования ещё не создан")
        return Response(ApprovalRouteSerializer(route).data)

    @extend_schema(
        summary="Согласовать текущий шаг",
        tags=["Approvals"],
        request=ApprovalDecisionSerializer,
        responses={200: ApprovalRouteSerializer},
    )
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        document = self.get_object()
        serializer = ApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        route = ApprovalService.approve(
            document, request.user, serializer.validated_data["comment"]
        )
        return Response(ApprovalRouteSerializer(route).data)

    @extend_schema(
        summary="Вернуть документ автору",
        tags=["Approvals"],
        request=ApprovalReturnSerializer,
        responses={200: ApprovalRouteSerializer},
    )
    @action(detail=True, methods=["post"], url_path="return")
    def return_document(self, request, pk=None):
        document = self.get_object()
        serializer = ApprovalReturnSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        route = ApprovalService.return_document(
            document, request.user, serializer.validated_data["comment"]
        )
        return Response(ApprovalRouteSerializer(route).data)

    @extend_schema(
        summary="Файлы документа",
        tags=["Document files"],
        request=DocumentFileUploadSerializer,
        responses={200: DocumentFileSerializer(many=True), 201: DocumentFileSerializer},
    )
    @action(detail=True, methods=["get", "post"])
    def files(self, request, pk=None):
        document = self.get_object()
        if request.method == "POST":
            upload_serializer = DocumentFileUploadSerializer(data=request.data)
            upload_serializer.is_valid(raise_exception=True)
            document_file = FileService.upload(
                document=document,
                uploaded_file=upload_serializer.validated_data["file"],
                user=request.user,
                is_main=upload_serializer.validated_data["is_main"],
            )
            return Response(
                DocumentFileSerializer(document_file, context=self.get_serializer_context()).data,
                status=status.HTTP_201_CREATED,
            )

        queryset = document.files.select_related("uploaded_by")
        page = self.paginate_queryset(queryset)
        serializer = DocumentFileSerializer(
            page if page is not None else queryset,
            many=True,
            context=self.get_serializer_context(),
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @extend_schema(
        summary="Комментарии документа",
        tags=["Document comments"],
        request=DocumentCommentCreateSerializer,
        responses={200: DocumentCommentSerializer(many=True), 201: DocumentCommentSerializer},
    )
    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        document = self.get_object()
        if request.method == "POST":
            input_serializer = DocumentCommentCreateSerializer(data=request.data)
            input_serializer.is_valid(raise_exception=True)
            comment = CommentService.create(
                document, request.user, input_serializer.validated_data["text"]
            )
            return Response(
                DocumentCommentSerializer(comment).data,
                status=status.HTTP_201_CREATED,
            )

        queryset = document.comments.select_related("author")
        page = self.paginate_queryset(queryset)
        serializer = DocumentCommentSerializer(page if page is not None else queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @extend_schema(
        summary="История документа",
        tags=["Document history"],
        responses={200: DocumentHistorySerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        document = self.get_object()
        queryset = document.history.select_related("user")
        page = self.paginate_queryset(queryset)
        serializer = DocumentHistorySerializer(page if page is not None else queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class DocumentFileViewSet(mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = DocumentFile.objects.none()
    serializer_class = DocumentFileSerializer
    permission_classes = [IsAuthenticated, HasPermissionPerAction]
    permission_map = {
        "destroy": "documents.create",
        "download": "documents.view",
    }
    http_method_names = ["get", "delete", "head", "options"]

    def get_queryset(self):
        queryset = DocumentFile.objects.select_related(
            "document", "document__category", "uploaded_by"
        )
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        visible_documents = DocumentAccessService.visible_to(self.request.user)
        return queryset.filter(document__in=visible_documents)

    def perform_destroy(self, instance):
        FileService.delete(instance, self.request.user)

    @extend_schema(summary="Скачать файл документа", tags=["Document files"])
    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        document_file = self.get_object()
        response = FileResponse(
            document_file.file.open("rb"),
            as_attachment=True,
            filename=document_file.original_name,
            content_type=document_file.mime_type,
        )
        response["Content-Length"] = document_file.size
        return response


class DocumentCommentViewSet(viewsets.GenericViewSet):
    queryset = DocumentComment.objects.none()
    serializer_class = DocumentCommentSerializer
    permission_classes = [IsAuthenticated, HasPermissionPerAction]
    permission_map = {
        "partial_update": "documents.view",
        "destroy": "documents.view",
    }
    http_method_names = ["patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = DocumentComment.objects.select_related("document", "author")
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        visible_documents = DocumentAccessService.visible_to(self.request.user)
        return queryset.filter(document__in=visible_documents)

    @extend_schema(
        summary="Изменить комментарий",
        tags=["Document comments"],
        request=DocumentCommentCreateSerializer,
        responses={200: DocumentCommentSerializer},
    )
    def partial_update(self, request, *args, **kwargs):
        comment = self.get_object()
        serializer = DocumentCommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = CommentService.update(comment, request.user, serializer.validated_data["text"])
        return Response(DocumentCommentSerializer(comment).data)

    def destroy(self, request, *args, **kwargs):
        comment = self.get_object()
        CommentService.delete(comment, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
