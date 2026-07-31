from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import DocumentCategory, DocumentCategoryStatus


class DocumentCategoryService:
    @staticmethod
    @transaction.atomic
    def set_status(category: DocumentCategory, status: str, user) -> DocumentCategory:
        category.status = status
        category.updated_by = user
        category.save(update_fields=["status", "updated_by", "updated_at"])
        return category

    @staticmethod
    @transaction.atomic
    def delete(category: DocumentCategory) -> None:
        if hasattr(category, "documents") and category.documents.exists():
            raise ValidationError(
                "Нельзя удалить категорию с документами. Используйте деактивацию."
            )
        category.delete()

    @classmethod
    def activate(cls, category: DocumentCategory, user) -> DocumentCategory:
        return cls.set_status(category, DocumentCategoryStatus.ACTIVE, user)

    @classmethod
    def deactivate(cls, category: DocumentCategory, user) -> DocumentCategory:
        return cls.set_status(category, DocumentCategoryStatus.INACTIVE, user)
