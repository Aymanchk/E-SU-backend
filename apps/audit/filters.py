import django_filters

from .constants import AuditAction, AuditResult
from .models import AuditLog


class AuditLogFilter(django_filters.FilterSet):
    user = django_filters.UUIDFilter(field_name="user__id")
    user_email = django_filters.CharFilter(field_name="user__email", lookup_expr="icontains")
    action = django_filters.MultipleChoiceFilter(choices=AuditAction.choices)
    object_type = django_filters.CharFilter(lookup_expr="iexact")
    object_id = django_filters.CharFilter()
    result = django_filters.ChoiceFilter(choices=AuditResult.choices)
    ip_address = django_filters.CharFilter()
    date_from = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    date_to = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = AuditLog
        fields = ["user", "action", "object_type", "object_id", "result"]
