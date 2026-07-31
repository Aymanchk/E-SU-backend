import django_filters

from .models import DocumentCategory, DocumentCategoryStatus


class DocumentCategoryFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    code = django_filters.CharFilter(lookup_expr="iexact")
    status = django_filters.ChoiceFilter(choices=DocumentCategoryStatus.choices)
    department = django_filters.UUIDFilter(field_name="allowed_departments__id")

    class Meta:
        model = DocumentCategory
        fields = ["name", "code", "status", "department"]
