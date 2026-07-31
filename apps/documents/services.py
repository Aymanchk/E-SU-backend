from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import (
    Document,
    DocumentCategory,
    DocumentCategoryStatus,
    DocumentNumberCounter,
    DocumentStatus,
)


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


class DocumentService:
    EDITABLE_STATUSES = {DocumentStatus.DRAFT, DocumentStatus.RETURNED}

    @staticmethod
    def visible_to(user, queryset: QuerySet | None = None) -> QuerySet:
        queryset = queryset if queryset is not None else Document.objects.all()
        if user.is_superuser or user.is_admin_role:
            return queryset

        role_code = user.role.code if user.role_id else None
        own_or_responsible = Q(author=user) | Q(responsible=user)
        if role_code == "manager":
            return queryset.filter(own_or_responsible | Q(department=user.department)).distinct()
        if role_code == "office":
            return queryset.filter(
                own_or_responsible
                | Q(
                    status__in=[
                        DocumentStatus.IN_REVIEW,
                        DocumentStatus.APPROVED,
                        DocumentStatus.COMPLETED,
                        DocumentStatus.OVERDUE,
                        DocumentStatus.ARCHIVED,
                    ]
                )
            ).distinct()
        return queryset.filter(own_or_responsible).distinct()

    @classmethod
    def ensure_can_edit(cls, document: Document, user) -> None:
        if document.status not in cls.EDITABLE_STATUSES:
            raise ValidationError("Документ в этом статусе нельзя редактировать")
        if not (user.is_admin_role or document.author_id == user.id):
            raise PermissionDenied("Редактировать документ может только автор или администратор")

    @classmethod
    def ensure_can_delete(cls, document: Document, user) -> None:
        if document.status != DocumentStatus.DRAFT:
            raise ValidationError("После отправки документ нельзя удалить")
        if not (user.is_admin_role or document.author_id == user.id):
            raise PermissionDenied("Удалить документ может только автор или администратор")

    @classmethod
    @transaction.atomic
    def submit(cls, document: Document, user) -> Document:
        cls.ensure_can_edit(document, user)
        document.status = DocumentStatus.IN_REVIEW
        document.submitted_at = timezone.now()
        document.current_approval_step = None
        document.save(
            update_fields=["status", "submitted_at", "current_approval_step", "updated_at"]
        )
        return document

    @staticmethod
    @transaction.atomic
    def complete(document: Document, user) -> Document:
        if document.status != DocumentStatus.APPROVED:
            raise ValidationError("Завершить можно только согласованный документ")
        if not (
            user.is_admin_role
            or document.responsible_id == user.id
            or user.has_permission("documents.edit")
        ):
            raise PermissionDenied("Недостаточно прав для завершения документа")
        document.status = DocumentStatus.COMPLETED
        document.completed_at = timezone.now()
        document.save(update_fields=["status", "completed_at", "updated_at"])
        return document

    @staticmethod
    @transaction.atomic
    def archive(document: Document, user) -> Document:
        if document.status not in {DocumentStatus.APPROVED, DocumentStatus.COMPLETED}:
            raise ValidationError("Архивировать можно согласованный или завершённый документ")
        if not (user.is_admin_role or user.has_permission("documents.archive")):
            raise PermissionDenied("Недостаточно прав для архивирования документа")
        document.status = DocumentStatus.ARCHIVED
        document.archived_at = timezone.now()
        document.save(update_fields=["status", "archived_at", "updated_at"])
        return document

    @staticmethod
    @transaction.atomic
    def restore(document: Document, user) -> Document:
        if document.status != DocumentStatus.ARCHIVED:
            raise ValidationError("Документ не находится в архиве")
        if not (user.is_admin_role or user.has_permission("documents.archive")):
            raise PermissionDenied("Недостаточно прав для восстановления документа")
        document.status = (
            DocumentStatus.COMPLETED if document.completed_at else DocumentStatus.APPROVED
        )
        document.archived_at = None
        document.save(update_fields=["status", "archived_at", "updated_at"])
        return document


class RegistrationService:
    @staticmethod
    def _locked_counter(category: DocumentCategory, year: int) -> DocumentNumberCounter:
        try:
            return DocumentNumberCounter.objects.select_for_update().get(
                category=category, year=year
            )
        except DocumentNumberCounter.DoesNotExist:
            try:
                # Savepoint keeps the outer transaction usable if another request
                # creates the same unique counter at exactly this moment.
                with transaction.atomic():
                    return DocumentNumberCounter.objects.create(
                        category=category, year=year, last_number=0
                    )
            except IntegrityError:
                return DocumentNumberCounter.objects.select_for_update().get(
                    category=category, year=year
                )

    @classmethod
    @transaction.atomic
    def register(cls, document: Document, user) -> Document:
        if not (user.is_admin_role or user.has_permission("documents.register")):
            raise PermissionDenied("Недостаточно прав для регистрации документа")

        document = (
            Document.objects.select_for_update()
            .select_related("category")
            .get(pk=document.pk)
        )
        if document.registration_number:
            raise ValidationError("Документ уже зарегистрирован")
        if document.status != DocumentStatus.APPROVED:
            raise ValidationError("Зарегистрировать можно только согласованный документ")

        year = timezone.localdate().year
        counter = cls._locked_counter(document.category, year)
        counter.last_number += 1
        counter.save(update_fields=["last_number", "updated_at"])

        category_code = document.category.code.upper()
        document.registration_number = (
            f"ESU-{category_code}-{year}-{counter.last_number:06d}"
        )
        document.save(update_fields=["registration_number", "updated_at"])
        return document
