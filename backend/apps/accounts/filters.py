import django_filters
from django.db.models import Q

from .models import User, UserStatus


class UserFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search", label="Поиск по ФИО и email")
    department = django_filters.UUIDFilter(field_name="department__id")
    department_code = django_filters.CharFilter(field_name="department__code")
    role = django_filters.CharFilter(field_name="role__code")
    status = django_filters.ChoiceFilter(choices=UserStatus.choices)
    position = django_filters.CharFilter(lookup_expr="icontains")
    is_active = django_filters.BooleanFilter()
    manager = django_filters.UUIDFilter(field_name="manager__id")

    class Meta:
        model = User
        fields = ["department", "role", "status", "position", "is_active"]

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(first_name__icontains=value)
            | Q(last_name__icontains=value)
            | Q(middle_name__icontains=value)
            | Q(email__icontains=value)
        )
