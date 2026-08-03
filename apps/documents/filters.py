import django_filters

from .models import (
    Document,
    DocumentCategory,
    DocumentCategoryStatus,
    DocumentPriority,
    DocumentStatus,
)


class DocumentCategoryFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    code = django_filters.CharFilter(lookup_expr="iexact")
    status = django_filters.ChoiceFilter(choices=DocumentCategoryStatus.choices)
    department = django_filters.UUIDFilter(field_name="allowed_departments__id")

    class Meta:
        model = DocumentCategory
        fields = ["name", "code", "status", "department"]


class DocumentFilter(django_filters.FilterSet):
    registration_number = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.ChoiceFilter(choices=DocumentStatus.choices)
    category = django_filters.UUIDFilter(field_name="category_id")
    author = django_filters.UUIDFilter(field_name="author_id")
    department = django_filters.UUIDFilter(field_name="department_id")
    responsible = django_filters.UUIDFilter(field_name="responsible_id")
    priority = django_filters.ChoiceFilter(choices=DocumentPriority.choices)
    created_from = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_to = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")
    deadline_from = django_filters.IsoDateTimeFilter(field_name="deadline", lookup_expr="gte")
    deadline_to = django_filters.IsoDateTimeFilter(field_name="deadline", lookup_expr="lte")

    class Meta:
        model = Document
        fields = [
            "registration_number",
            "status",
            "category",
            "author",
            "department",
            "responsible",
            "priority",
        ]
