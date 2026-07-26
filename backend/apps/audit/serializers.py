from rest_framework import serializers

from .models import AuditLog


class AuditUserSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    full_name = serializers.CharField(read_only=True)


class AuditLogSerializer(serializers.ModelSerializer):
    user = AuditUserSerializer(read_only=True)
    action_display = serializers.CharField(source="get_action_display", read_only=True)
    result_display = serializers.CharField(source="get_result_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "user",
            "action",
            "action_display",
            "object_type",
            "object_id",
            "description",
            "ip_address",
            "user_agent",
            "result",
            "result_display",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields
