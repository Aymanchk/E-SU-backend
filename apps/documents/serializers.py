from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import User, UserStatus
from apps.accounts.serializers import RoleShortSerializer, UserShortSerializer
from apps.organizations.serializers import DepartmentShortSerializer

from .models import (
    ApprovalAction,
    ApprovalRoute,
    ApprovalStep,
    Document,
    DocumentCategory,
    DocumentCategoryStatus,
    DocumentComment,
    DocumentFile,
    DocumentHistory,
    DocumentStatus,
)


class DocumentCategorySerializer(serializers.ModelSerializer):
    allowed_departments_details = DepartmentShortSerializer(
        source="allowed_departments", many=True, read_only=True
    )

    class Meta:
        model = DocumentCategory
        fields = [
            "id",
            "name",
            "code",
            "description",
            "retention_period_days",
            "allowed_departments",
            "allowed_departments_details",
            "status",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def validate_code(self, value):
        queryset = DocumentCategory.all_objects.filter(code=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Категория с таким кодом уже существует")
        return value


class DocumentCategoryShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentCategory
        fields = ["id", "name", "code", "status"]


class DocumentListSerializer(serializers.ModelSerializer):
    category = DocumentCategoryShortSerializer(read_only=True)
    author = UserShortSerializer(read_only=True)
    department = DepartmentShortSerializer(read_only=True)
    responsible = UserShortSerializer(read_only=True)

    class Meta:
        model = Document
        fields = [
            "id",
            "registration_number",
            "title",
            "document_type",
            "category",
            "author",
            "department",
            "responsible",
            "priority",
            "status",
            "deadline",
            "submitted_at",
            "approved_at",
            "completed_at",
            "archived_at",
            "current_approval_step",
            "created_at",
            "updated_at",
        ]


class DocumentDetailSerializer(DocumentListSerializer):
    class Meta(DocumentListSerializer.Meta):
        fields = DocumentListSerializer.Meta.fields + ["description"]


class DocumentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "description",
            "document_type",
            "category",
            "department",
            "responsible",
            "priority",
            "deadline",
        ]
        read_only_fields = ["id"]

    def validate_category(self, category):
        if category.status != DocumentCategoryStatus.ACTIVE:
            raise serializers.ValidationError("Нельзя выбрать неактивную категорию")
        return category

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user
        department = attrs.get("department", getattr(self.instance, "department", None))
        category = attrs.get("category", getattr(self.instance, "category", None))

        if not user.is_admin_role and department != user.department:
            raise serializers.ValidationError(
                {"department": "Документ можно создать только в своём подразделении"}
            )

        if (
            category
            and category.allowed_departments.exists()
            and (
                not department or not category.allowed_departments.filter(pk=department.pk).exists()
            )
        ):
            raise serializers.ValidationError(
                {"category": "Категория недоступна выбранному подразделению"}
            )

        if self.instance and self.instance.status not in (
            DocumentStatus.DRAFT,
            DocumentStatus.RETURNED,
        ):
            raise serializers.ValidationError("Документ в этом статусе нельзя редактировать")
        return attrs


class DocumentFileSerializer(serializers.ModelSerializer):
    uploaded_by = UserShortSerializer(read_only=True)

    class Meta:
        model = DocumentFile
        fields = [
            "id",
            "document",
            "file",
            "original_name",
            "file_type",
            "mime_type",
            "size",
            "is_main",
            "uploaded_by",
            "created_at",
        ]
        read_only_fields = fields


class DocumentFileUploadSerializer(serializers.Serializer):
    file = serializers.FileField(write_only=True)
    is_main = serializers.BooleanField(default=False, required=False)


class DocumentSubmitSerializer(serializers.Serializer):
    approvers = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(status=UserStatus.ACTIVE, is_active=True).select_related(
            "role"
        ),
        many=True,
    )

    def validate_approvers(self, value):
        ids = [approver.id for approver in value]
        if not ids:
            raise serializers.ValidationError("Добавьте хотя бы одного согласующего")
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Согласующие в маршруте не должны повторяться")
        return value


class ApprovalDecisionSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class ApprovalReturnSerializer(serializers.Serializer):
    comment = serializers.CharField(required=True, allow_blank=False)


class ApprovalActionSerializer(serializers.ModelSerializer):
    actor = UserShortSerializer(read_only=True)

    class Meta:
        model = ApprovalAction
        fields = ["id", "step", "actor", "action", "comment", "created_at"]


class ApprovalStepSerializer(serializers.ModelSerializer):
    approver = UserShortSerializer(read_only=True)
    role = RoleShortSerializer(read_only=True)

    class Meta:
        model = ApprovalStep
        fields = [
            "id",
            "order",
            "approver",
            "role",
            "status",
            "comment",
            "acted_at",
            "created_at",
        ]


class ApprovalRouteSerializer(serializers.ModelSerializer):
    created_by = UserShortSerializer(read_only=True)
    steps = ApprovalStepSerializer(many=True, read_only=True)
    actions = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalRoute
        fields = [
            "id",
            "document",
            "status",
            "created_by",
            "created_at",
            "completed_at",
            "steps",
            "actions",
        ]

    @extend_schema_field(ApprovalActionSerializer(many=True))
    def get_actions(self, obj):
        actions = ApprovalAction.objects.filter(step__route=obj).select_related("actor")
        return ApprovalActionSerializer(actions, many=True).data


class DocumentCommentSerializer(serializers.ModelSerializer):
    author = UserShortSerializer(read_only=True)

    class Meta:
        model = DocumentComment
        fields = [
            "id",
            "document",
            "author",
            "text",
            "comment_type",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "document",
            "author",
            "comment_type",
            "created_at",
            "updated_at",
        ]

    def validate_text(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Комментарий не может быть пустым")
        return value


class DocumentCommentCreateSerializer(serializers.Serializer):
    text = serializers.CharField(allow_blank=False)

    def validate_text(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Комментарий не может быть пустым")
        return value


class DocumentHistorySerializer(serializers.ModelSerializer):
    user = UserShortSerializer(read_only=True)

    class Meta:
        model = DocumentHistory
        fields = [
            "id",
            "document",
            "user",
            "action",
            "old_values",
            "new_values",
            "description",
            "created_at",
        ]
        read_only_fields = fields


class DashboardSerializer(serializers.Serializer):
    total_documents = serializers.IntegerField()
    in_review = serializers.IntegerField()
    returned = serializers.IntegerField()
    overdue = serializers.IntegerField()
    completed = serializers.IntegerField()
    approval_tasks = serializers.IntegerField()
    recent_documents = DocumentListSerializer(many=True)
    upcoming_deadlines = DocumentListSerializer(many=True)
    recent_actions = DocumentHistorySerializer(many=True)
