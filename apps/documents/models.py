import uuid
from pathlib import Path

from django.db import models
from django.db.models import Q

from apps.common.models import SoftDeleteModel, TimeStampedModel, UUIDModel


class DocumentCategoryStatus(models.TextChoices):
    ACTIVE = "active", "Активна"
    INACTIVE = "inactive", "Неактивна"


class DocumentCategory(UUIDModel, TimeStampedModel, SoftDeleteModel):
    name = models.CharField("Название", max_length=200, db_index=True)
    code = models.SlugField("Код", max_length=50, unique=True, db_index=True)
    description = models.TextField("Описание", blank=True)
    retention_period_days = models.PositiveIntegerField("Срок хранения (дней)")
    allowed_departments = models.ManyToManyField(
        "organizations.Department",
        blank=True,
        related_name="document_categories",
        verbose_name="Разрешённые подразделения",
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=DocumentCategoryStatus.choices,
        default=DocumentCategoryStatus.ACTIVE,
        db_index=True,
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Категория документов"
        verbose_name_plural = "Категории документов"

    def __str__(self):
        return self.name


class DocumentPriority(models.TextChoices):
    LOW = "low", "Низкий"
    NORMAL = "normal", "Обычный"
    HIGH = "high", "Высокий"
    URGENT = "urgent", "Срочный"


class DocumentStatus(models.TextChoices):
    DRAFT = "draft", "Черновик"
    IN_REVIEW = "in_review", "На согласовании"
    RETURNED = "returned", "Возвращён"
    APPROVED = "approved", "Согласован"
    COMPLETED = "completed", "Завершён"
    OVERDUE = "overdue", "Просрочен"
    ARCHIVED = "archived", "В архиве"


class Document(UUIDModel, SoftDeleteModel):
    registration_number = models.CharField(
        "Регистрационный номер",
        max_length=100,
        null=True,
        blank=True,
        unique=True,
        db_index=True,
    )
    title = models.CharField("Название", max_length=255)
    description = models.TextField("Описание", blank=True)
    document_type = models.SlugField("Тип документа", max_length=50)
    category = models.ForeignKey(
        DocumentCategory,
        on_delete=models.PROTECT,
        related_name="documents",
        verbose_name="Категория",
    )
    author = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="authored_documents",
        verbose_name="Автор",
    )
    department = models.ForeignKey(
        "organizations.Department",
        on_delete=models.PROTECT,
        related_name="documents",
        verbose_name="Подразделение",
    )
    responsible = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="responsible_documents",
        verbose_name="Ответственный",
    )
    priority = models.CharField(
        "Приоритет",
        max_length=20,
        choices=DocumentPriority.choices,
        default=DocumentPriority.NORMAL,
        db_index=True,
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=DocumentStatus.choices,
        default=DocumentStatus.DRAFT,
        db_index=True,
    )
    deadline = models.DateTimeField("Дедлайн", null=True, blank=True, db_index=True)
    submitted_at = models.DateTimeField("Отправлен", null=True, blank=True)
    approved_at = models.DateTimeField("Согласован", null=True, blank=True)
    completed_at = models.DateTimeField("Завершён", null=True, blank=True)
    archived_at = models.DateTimeField("Архивирован", null=True, blank=True)
    current_approval_step = models.PositiveIntegerField(
        "Текущий шаг согласования", null=True, blank=True
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("Изменён", auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Документ"
        verbose_name_plural = "Документы"
        indexes = [
            models.Index(fields=["author", "status"]),
            models.Index(fields=["department", "status"]),
            models.Index(fields=["responsible", "status"]),
            models.Index(fields=["category", "status"]),
        ]

    def __str__(self):
        return self.registration_number or self.title


class DocumentNumberCounter(models.Model):
    category = models.ForeignKey(
        DocumentCategory,
        on_delete=models.PROTECT,
        related_name="number_counters",
        verbose_name="Категория",
    )
    year = models.PositiveSmallIntegerField("Год")
    last_number = models.PositiveIntegerField("Последний номер", default=0)
    updated_at = models.DateTimeField("Изменён", auto_now=True)

    class Meta:
        verbose_name = "Счётчик номеров документов"
        verbose_name_plural = "Счётчики номеров документов"
        constraints = [
            models.UniqueConstraint(
                fields=["category", "year"], name="unique_document_counter_category_year"
            )
        ]

    def __str__(self):
        return f"{self.category.code}:{self.year}:{self.last_number}"


def document_file_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"documents/{instance.document_id}/{uuid.uuid4().hex}{extension}"


class DocumentFile(UUIDModel):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="files",
        verbose_name="Документ",
    )
    file = models.FileField(
        "Файл", upload_to=document_file_upload_path, max_length=500
    )
    original_name = models.CharField("Исходное имя", max_length=255)
    file_type = models.CharField("Тип файла", max_length=20)
    mime_type = models.CharField("MIME-тип", max_length=150)
    size = models.PositiveBigIntegerField("Размер")
    is_main = models.BooleanField("Основной файл", default=False)
    uploaded_by = models.ForeignKey(
        "accounts.User",
        null=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_document_files",
        verbose_name="Загрузил",
    )
    created_at = models.DateTimeField("Загружен", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-is_main", "created_at"]
        verbose_name = "Файл документа"
        verbose_name_plural = "Файлы документов"
        constraints = [
            models.UniqueConstraint(
                fields=["document"],
                condition=Q(is_main=True),
                name="unique_main_file_per_document",
            )
        ]

    def __str__(self):
        return self.original_name
