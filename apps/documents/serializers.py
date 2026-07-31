from rest_framework import serializers

from apps.accounts.serializers import UserShortSerializer
from apps.organizations.serializers import DepartmentShortSerializer

from .models import (
    Document,
    DocumentCategory,
    DocumentCategoryStatus,
    DocumentFile,
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
                not department
                or not category.allowed_departments.filter(pk=department.pk).exists()
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
