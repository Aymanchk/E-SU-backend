from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import User, UserStatus
from apps.accounts.serializers import RoleShortSerializer, UserShortSerializer
from apps.notifications.serializers import NotificationSerializer
from apps.organizations.models import Department
from apps.organizations.serializers import DepartmentShortSerializer

from .models import (
    ApprovalAction,
    ApprovalRoute,
    ApprovalRouteTemplate,
    ApprovalRouteTemplateStep,
    ApprovalStep,
    ApprovalTemplateApproverType,
    ApprovalTemplateDepartmentRelation,
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
    document_count = serializers.IntegerField(read_only=True, default=0)
    approval_route_template = serializers.SerializerMethodField()

    class Meta:
        model = DocumentCategory
        fields = [
            "id",
            "name",
            "code",
            "description",
            "retention_period_days",
            "requires_file",
            "allowed_departments",
            "allowed_departments_details",
            "status",
            "document_count",
            "approval_route_template",
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

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_approval_route_template(self, obj):
        template = next(
            (item for item in obj.approval_route_templates.all() if item.is_active),
            None,
        )
        if template is None:
            return None
        return ApprovalRouteTemplateSerializer(template).data


class ApprovalRouteTemplateStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalRouteTemplateStep
        fields = [
            "id",
            "order",
            "approver_type",
            "role",
            "specific_user",
            "department_relation",
            "is_required",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        approver_type = attrs.get("approver_type")
        role = attrs.get("role")
        specific_user = attrs.get("specific_user")
        department_relation = attrs.get("department_relation", "")

        if attrs.get("order", 0) < 1:
            raise serializers.ValidationError({"order": "Порядок шага начинается с 1"})
        if approver_type == ApprovalTemplateApproverType.SPECIFIC_USER:
            if specific_user is None:
                raise serializers.ValidationError(
                    {"specific_user": "Укажите конкретного пользователя"}
                )
            if role or department_relation:
                raise serializers.ValidationError(
                    "Для specific_user нельзя указывать role или department_relation"
                )
        elif approver_type == ApprovalTemplateApproverType.ROLE:
            if role is None:
                raise serializers.ValidationError({"role": "Укажите роль согласующего"})
            if specific_user or department_relation:
                raise serializers.ValidationError(
                    "Для role нельзя указывать specific_user или department_relation"
                )
        elif approver_type == ApprovalTemplateApproverType.DEPARTMENT_MANAGER:
            if role or specific_user:
                raise serializers.ValidationError(
                    "Для department_manager нельзя указывать role или specific_user"
                )
            attrs["department_relation"] = (
                department_relation
                or ApprovalTemplateDepartmentRelation.DOCUMENT_DEPARTMENT
            )
        elif approver_type == ApprovalTemplateApproverType.DOCUMENT_RESPONSIBLE:
            if role or specific_user or department_relation:
                raise serializers.ValidationError(
                    "Для document_responsible дополнительные параметры не нужны"
                )
        return attrs


class ApprovalRouteTemplateSerializer(serializers.ModelSerializer):
    steps = ApprovalRouteTemplateStepSerializer(many=True)

    class Meta:
        model = ApprovalRouteTemplate
        fields = [
            "id",
            "category",
            "name",
            "is_active",
            "steps",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def validate(self, attrs):
        steps = attrs.get("steps")
        if self.instance is None and not steps:
            raise serializers.ValidationError({"steps": "Добавьте хотя бы один шаг"})
        if steps is not None:
            orders = [step["order"] for step in steps]
            if len(orders) != len(set(orders)):
                raise serializers.ValidationError(
                    {"steps": "Порядок шагов не должен повторяться"}
                )

        category = attrs.get("category", getattr(self.instance, "category", None))
        is_active = attrs.get("is_active", getattr(self.instance, "is_active", True))
        if category and is_active:
            active_templates = ApprovalRouteTemplate.objects.filter(
                category=category, is_active=True
            )
            if self.instance:
                active_templates = active_templates.exclude(pk=self.instance.pk)
            if active_templates.exists():
                raise serializers.ValidationError(
                    {"is_active": "У категории уже есть активный шаблон"}
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        steps = validated_data.pop("steps")
        template = ApprovalRouteTemplate.objects.create(**validated_data)
        ApprovalRouteTemplateStep.objects.bulk_create(
            [ApprovalRouteTemplateStep(template=template, **step) for step in steps]
        )
        return template

    @transaction.atomic
    def update(self, instance, validated_data):
        steps = validated_data.pop("steps", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if steps is not None:
            instance.steps.all().delete()
            ApprovalRouteTemplateStep.objects.bulk_create(
                [ApprovalRouteTemplateStep(template=instance, **step) for step in steps]
            )
        return instance


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
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=DocumentCategory.objects.all()
    )
    department_id = serializers.PrimaryKeyRelatedField(
        source="department", queryset=Department.objects.all()
    )
    responsible_id = serializers.PrimaryKeyRelatedField(
        source="responsible",
        queryset=User.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "description",
            "document_type",
            "category_id",
            "department_id",
            "responsible_id",
            "priority",
            "deadline",
        ]
        read_only_fields = ["id"]

    def to_internal_value(self, data):
        data = data.copy()
        aliases = {
            "category": "category_id",
            "department": "department_id",
            "responsible": "responsible_id",
        }
        for legacy_name, canonical_name in aliases.items():
            if legacy_name in data and canonical_name in data:
                if str(data[legacy_name]) != str(data[canonical_name]):
                    raise serializers.ValidationError(
                        {canonical_name: f"Нельзя передавать разные {legacy_name} и {canonical_name}"}
                    )
            elif legacy_name in data:
                data[canonical_name] = data[legacy_name]
        return super().to_internal_value(data)

    def validate_category_id(self, category):
        if category.status != DocumentCategoryStatus.ACTIVE:
            raise serializers.ValidationError("Нельзя выбрать неактивную категорию")
        return category

    def validate_responsible_id(self, responsible):
        if responsible is not None and (
            responsible.status != UserStatus.ACTIVE
            or not responsible.is_active
            or responsible.is_deleted
        ):
            raise serializers.ValidationError("Ответственный пользователь должен быть активен")
        return responsible

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user
        department = attrs.get("department", getattr(self.instance, "department", None))
        category = attrs.get("category", getattr(self.instance, "category", None))
        deadline = attrs.get("deadline")

        if self.instance is None and deadline and deadline <= timezone.now():
            raise serializers.ValidationError(
                {"deadline": "Срок исполнения не может находиться в прошлом"}
            )

        if not user.is_admin_role and user.department and department != user.department:
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
        required=False,
        default=list,
        help_text=(
            "Непустой список создаёт ручной маршрут и имеет приоритет. "
            "Если список не передан или пуст, используется активный шаблон категории."
        ),
    )

    def validate_approvers(self, value):
        ids = [approver.id for approver in value]
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
            "source",
            "template",
            "template_snapshot",
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


class DashboardCountersSerializer(serializers.Serializer):
    all = serializers.IntegerField()
    my = serializers.IntegerField()
    for_approval = serializers.IntegerField()
    returned = serializers.IntegerField()
    overdue = serializers.IntegerField()
    archived = serializers.IntegerField()


class DashboardQuickActionSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()
    url = serializers.CharField()


class DashboardSerializer(serializers.Serializer):
    counters = DashboardCountersSerializer()
    recent_documents = DocumentListSerializer(many=True)
    approval_documents = DocumentListSerializer(many=True)
    recent_notifications = NotificationSerializer(many=True)
    quick_actions = DashboardQuickActionSerializer(many=True)
