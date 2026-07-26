from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import SystemSetting


class SystemSettingSerializer(serializers.ModelSerializer):
    typed_value = serializers.SerializerMethodField()

    class Meta:
        model = SystemSetting
        fields = [
            "key",
            "value",
            "typed_value",
            "value_type",
            "description",
            "is_public",
            "updated_at",
        ]
        read_only_fields = ["key", "value_type", "description", "is_public", "updated_at"]

    @extend_schema_field(serializers.JSONField())
    def get_typed_value(self, obj):
        return obj.get_value()


class SystemSettingsUpdateSerializer(serializers.Serializer):
    """
    Принимает словарь вида {"max_file_size_mb": 50, "university_name": "..."}
    и обновляет несколько настроек за раз.
    """

    def to_internal_value(self, data):
        if not isinstance(data, dict) or not data:
            raise serializers.ValidationError('Ожидается непустой объект вида {"ключ": "значение"}')

        keys = set(data.keys())
        existing = set(SystemSetting.objects.filter(key__in=keys).values_list("key", flat=True))
        unknown = keys - existing
        if unknown:
            raise serializers.ValidationError(
                {"detail": f"Неизвестные настройки: {', '.join(sorted(unknown))}"}
            )

        return data
