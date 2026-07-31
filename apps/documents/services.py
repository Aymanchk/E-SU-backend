from pathlib import Path
from zipfile import BadZipFile, ZipFile

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import (
    Document,
    DocumentCategory,
    DocumentCategoryStatus,
    DocumentFile,
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


class FileService:
    ALLOWED_MIME_TYPES = {
        ".pdf": {"application/pdf"},
        ".doc": {"application/msword"},
        ".docx": {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        },
        ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        ".png": {"image/png"},
        ".jpg": {"image/jpeg"},
        ".jpeg": {"image/jpeg"},
    }

    @staticmethod
    def _has_valid_signature(uploaded_file, extension: str) -> bool:
        position = uploaded_file.tell()
        try:
            header = uploaded_file.read(8)
            uploaded_file.seek(0)
            if extension == ".pdf":
                return header.startswith(b"%PDF-")
            if extension == ".png":
                return header == b"\x89PNG\r\n\x1a\n"
            if extension in {".jpg", ".jpeg"}:
                return header.startswith(b"\xff\xd8\xff")
            if extension == ".doc":
                return header == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
            if extension in {".docx", ".xlsx"}:
                try:
                    with ZipFile(uploaded_file) as archive:
                        prefix = "word/" if extension == ".docx" else "xl/"
                        return any(name.startswith(prefix) for name in archive.namelist())
                except BadZipFile:
                    return False
            return False
        finally:
            uploaded_file.seek(position)

    @classmethod
    def validate_upload(cls, uploaded_file) -> tuple[str, str]:
        original_name = Path(uploaded_file.name).name
        extension = Path(original_name).suffix.lower()
        if extension not in cls.ALLOWED_MIME_TYPES:
            raise ValidationError(
                "Недопустимый формат файла. Разрешены PDF, DOC, DOCX, XLSX, PNG, JPG и JPEG."
            )

        mime_type = (getattr(uploaded_file, "content_type", "") or "").lower()
        if mime_type not in cls.ALLOWED_MIME_TYPES[extension]:
            raise ValidationError("MIME-тип файла не соответствует его расширению")

        if uploaded_file.size > settings.MAX_DOCUMENT_FILE_SIZE:
            max_megabytes = settings.MAX_DOCUMENT_FILE_SIZE // (1024 * 1024)
            raise ValidationError(f"Размер файла не должен превышать {max_megabytes} МБ")
        if uploaded_file.size == 0:
            raise ValidationError("Нельзя загрузить пустой файл")
        if not cls._has_valid_signature(uploaded_file, extension):
            raise ValidationError("Содержимое файла не соответствует заявленному формату")
        return extension.removeprefix("."), mime_type

    @classmethod
    @transaction.atomic
    def upload(cls, document: Document, uploaded_file, user, is_main=False) -> DocumentFile:
        DocumentService.ensure_can_edit(document, user)
        file_type, mime_type = cls.validate_upload(uploaded_file)

        existing_files = document.files.exists()
        make_main = is_main or not existing_files
        if make_main:
            document.files.filter(is_main=True).update(is_main=False)

        return DocumentFile.objects.create(
            document=document,
            file=uploaded_file,
            original_name=Path(uploaded_file.name).name,
            file_type=file_type,
            mime_type=mime_type,
            size=uploaded_file.size,
            is_main=make_main,
            uploaded_by=user,
        )

    @staticmethod
    @transaction.atomic
    def delete(document_file: DocumentFile, user) -> None:
        DocumentService.ensure_can_edit(document_file.document, user)
        storage = document_file.file.storage
        stored_name = document_file.file.name
        document_file.delete()
        transaction.on_commit(lambda: storage.delete(stored_name))
