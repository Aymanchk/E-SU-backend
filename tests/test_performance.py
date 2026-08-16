import pytest
from django.db import connection

from apps.documents.models import (
    ApprovalStep,
    Document,
    DocumentCategory,
    DocumentHistory,
)
from apps.documents.serializers import DocumentDetailSerializer, DocumentListSerializer
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


def model_index_fields(model):
    return {tuple(index.fields) for index in model._meta.indexes}


def test_required_composite_indexes_are_declared():
    assert {
        ("status", "deadline"),
        ("status", "created_at"),
        ("author", "created_at"),
        ("responsible", "status"),
    } <= model_index_fields(Document)
    assert ("approver", "status") in model_index_fields(ApprovalStep)
    assert ("recipient", "is_read", "created_at") in model_index_fields(Notification)
    assert ("document", "created_at") in model_index_fields(DocumentHistory)


def test_document_performance_indexes_exist_in_database():
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(
            cursor, Document._meta.db_table
        )

    for name in {
        "doc_status_deadline_idx",
        "doc_status_created_idx",
        "doc_author_created_idx",
    }:
        assert constraints[name]["index"] is True


def test_document_serializers_have_bounded_queries(
    django_assert_max_num_queries,
    admin,
    employee,
    child_department,
):
    category = DocumentCategory.objects.create(
        name="Производительность",
        code="performance",
        retention_period_days=365,
        created_by=admin,
        updated_by=admin,
    )
    Document.objects.bulk_create(
        [
            Document(
                title=f"Документ {index}",
                document_type="memo",
                category=category,
                author=employee,
                department=child_department,
                responsible=employee,
            )
            for index in range(20)
        ]
    )
    queryset = Document.objects.select_related(
        "category", "author", "department", "responsible"
    )

    with django_assert_max_num_queries(1):
        list_data = DocumentListSerializer(queryset, many=True).data
    with django_assert_max_num_queries(1):
        detail = Document.objects.select_related(
            "category", "author", "department", "responsible"
        ).first()
        detail_data = DocumentDetailSerializer(detail).data

    assert len(list_data) == 20
    assert detail_data["description"] == ""
