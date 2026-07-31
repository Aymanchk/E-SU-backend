from rest_framework import serializers

from apps.organizations.serializers import DepartmentShortSerializer

from .models import DocumentCategory


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
