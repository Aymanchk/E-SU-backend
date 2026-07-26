import django_filters

from .models import Department


class DepartmentFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    code = django_filters.CharFilter(lookup_expr="iexact")
    status = django_filters.ChoiceFilter(choices=Department._meta.get_field("status").choices)
    manager = django_filters.UUIDFilter(field_name="manager__id")
    parent = django_filters.UUIDFilter(field_name="parent__id")
    root_only = django_filters.BooleanFilter(method="filter_root_only", label="Только корневые")

    class Meta:
        model = Department
        fields = ["name", "code", "status", "manager", "parent"]

    def filter_root_only(self, queryset, name, value):
        if value:
            return queryset.filter(parent__isnull=True)
        return queryset
