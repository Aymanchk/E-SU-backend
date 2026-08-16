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
    requires_file = models.BooleanField("Обязательный файл", default=False)
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


class ApprovalTemplateApproverType(models.TextChoices):
    SPECIFIC_USER = "specific_user", "Конкретный пользователь"
    ROLE = "role", "Роль"
    DEPARTMENT_MANAGER = "department_manager", "Руководитель подразделения"
    DOCUMENT_RESPONSIBLE = "document_responsible", "Ответственный за документ"


class ApprovalTemplateDepartmentRelation(models.TextChoices):
    AUTHOR_DEPARTMENT = "author_department", "Подразделение автора"
    DOCUMENT_DEPARTMENT = "document_department", "Подразделение документа"


class ApprovalRouteTemplate(UUIDModel, TimeStampedModel):
    category = models.ForeignKey(
        DocumentCategory,
        on_delete=models.CASCADE,
        related_name="approval_route_templates",
        verbose_name="Категория",
    )
    name = models.CharField("Название", max_length=200)
    is_active = models.BooleanField("Активен", default=True, db_index=True)

    class Meta:
        ordering = ["category", "name"]
        verbose_name = "Шаблон маршрута согласования"
        verbose_name_plural = "Шаблоны маршрутов согласования"
        constraints = [
            models.UniqueConstraint(
                fields=["category"],
                condition=Q(is_active=True),
                name="unique_active_route_template_category",
            )
        ]

    def __str__(self):
        return f"{self.category}: {self.name}"


class ApprovalRouteTemplateStep(UUIDModel):
    template = models.ForeignKey(
        ApprovalRouteTemplate,
        on_delete=models.CASCADE,
        related_name="steps",
        verbose_name="Шаблон",
    )
    order = models.PositiveIntegerField("Порядок")
    approver_type = models.CharField(
        "Тип согласующего",
        max_length=30,
        choices=ApprovalTemplateApproverType.choices,
    )
    role = models.ForeignKey(
        "accounts.Role",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approval_template_steps",
        verbose_name="Роль",
    )
    specific_user = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approval_template_steps",
        verbose_name="Конкретный пользователь",
    )
    department_relation = models.CharField(
        "Связь с подразделением",
        max_length=30,
        choices=ApprovalTemplateDepartmentRelation.choices,
        blank=True,
    )
    is_required = models.BooleanField("Обязательный шаг", default=True)

    class Meta:
        ordering = ["order"]
        verbose_name = "Шаг шаблона согласования"
        verbose_name_plural = "Шаги шаблона согласования"
        constraints = [
            models.UniqueConstraint(
                fields=["template", "order"],
                name="unique_route_template_step_order",
            )
        ]

    def __str__(self):
        return f"{self.template}: {self.order}"


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
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        "organizations.Department",
        on_delete=models.PROTECT,
        related_name="document_number_counters",
        verbose_name="Подразделение",
        null=True,
        blank=True,
    )
    year = models.PositiveSmallIntegerField("Год")
    last_number = models.PositiveIntegerField("Последний номер", default=0)
    updated_at = models.DateTimeField("Изменён", auto_now=True)

    class Meta:
        verbose_name = "Счётчик номеров документов"
        verbose_name_plural = "Счётчики номеров документов"
        constraints = [
            models.UniqueConstraint(
                fields=["department", "year"],
                condition=Q(department__isnull=False),
                name="unique_document_counter_department_year",
            )
        ]

    def __str__(self):
        owner = self.department or self.category
        return f"{owner}:{self.year}:{self.last_number}"


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
    file = models.FileField("Файл", upload_to=document_file_upload_path, max_length=500)
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


class ApprovalRouteStatus(models.TextChoices):
    ACTIVE = "active", "Активен"
    COMPLETED = "completed", "Завершён"
    RETURNED = "returned", "Возвращён"
    CANCELLED = "cancelled", "Отменён"


class ApprovalRouteSource(models.TextChoices):
    MANUAL = "manual", "Ручной маршрут"
    CATEGORY_TEMPLATE = "category_template", "Шаблон категории"


class ApprovalStepStatus(models.TextChoices):
    PENDING = "pending", "Ожидает"
    CURRENT = "current", "Текущий"
    APPROVED = "approved", "Согласован"
    RETURNED = "returned", "Возвращён"
    CANCELLED = "cancelled", "Отменён"


class ApprovalActionType(models.TextChoices):
    APPROVE = "approve", "Согласовать"
    RETURN = "return", "Вернуть"


class ApprovalRoute(UUIDModel):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="approval_routes",
        verbose_name="Документ",
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=ApprovalRouteStatus.choices,
        default=ApprovalRouteStatus.ACTIVE,
        db_index=True,
    )
    source = models.CharField(
        "Источник маршрута",
        max_length=30,
        choices=ApprovalRouteSource.choices,
        default=ApprovalRouteSource.MANUAL,
    )
    template = models.ForeignKey(
        ApprovalRouteTemplate,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approval_routes",
        verbose_name="Исходный шаблон",
    )
    template_snapshot = models.JSONField(
        "Снимок шаблона", default=dict, blank=True
    )
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        on_delete=models.SET_NULL,
        related_name="created_approval_routes",
        verbose_name="Создал",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField("Завершён", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Маршрут согласования"
        verbose_name_plural = "Маршруты согласования"

    def __str__(self):
        return f"{self.document}: {self.status}"


class ApprovalStep(UUIDModel):
    route = models.ForeignKey(
        ApprovalRoute,
        on_delete=models.CASCADE,
        related_name="steps",
        verbose_name="Маршрут",
    )
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="approval_steps",
        verbose_name="Документ",
    )
    order = models.PositiveIntegerField("Порядок")
    approver = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="approval_steps",
        verbose_name="Согласующий",
    )
    role = models.ForeignKey(
        "accounts.Role",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approval_steps",
        verbose_name="Роль на момент назначения",
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=ApprovalStepStatus.choices,
        default=ApprovalStepStatus.PENDING,
        db_index=True,
    )
    comment = models.TextField("Комментарий", blank=True)
    acted_at = models.DateTimeField("Дата действия", null=True, blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        ordering = ["order"]
        verbose_name = "Шаг согласования"
        verbose_name_plural = "Шаги согласования"
        constraints = [
            models.UniqueConstraint(fields=["route", "order"], name="unique_approval_step_order")
        ]
        indexes = [
            models.Index(fields=["document", "status"]),
            models.Index(fields=["approver", "status"]),
        ]

    def __str__(self):
        return f"{self.document}: {self.order} — {self.approver}"


class ApprovalAction(UUIDModel):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="approval_actions",
        verbose_name="Документ",
    )
    step = models.ForeignKey(
        ApprovalStep,
        on_delete=models.PROTECT,
        related_name="actions",
        verbose_name="Шаг",
    )
    actor = models.ForeignKey(
        "accounts.User",
        null=True,
        on_delete=models.SET_NULL,
        related_name="approval_actions",
        verbose_name="Пользователь",
    )
    action = models.CharField(
        "Действие", max_length=20, choices=ApprovalActionType.choices, db_index=True
    )
    comment = models.TextField("Комментарий", blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Действие согласования"
        verbose_name_plural = "Действия согласования"

    def __str__(self):
        return f"{self.document}: {self.action}"


class DocumentCommentType(models.TextChoices):
    GENERAL = "general", "Обычный"
    APPROVAL = "approval", "Комментарий согласования"
    RETURN_REASON = "return_reason", "Причина возврата"
    SYSTEM = "system", "Системный"


class DocumentComment(UUIDModel):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="Документ",
    )
    author = models.ForeignKey(
        "accounts.User",
        null=True,
        on_delete=models.SET_NULL,
        related_name="document_comments",
        verbose_name="Автор",
    )
    text = models.TextField("Текст")
    comment_type = models.CharField(
        "Тип",
        max_length=30,
        choices=DocumentCommentType.choices,
        default=DocumentCommentType.GENERAL,
        db_index=True,
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("Изменён", auto_now=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Комментарий документа"
        verbose_name_plural = "Комментарии документов"

    def __str__(self):
        return self.text[:80]


class DocumentHistoryAction(models.TextChoices):
    CREATED = "created", "Создание"
    UPDATED = "updated", "Редактирование"
    FILE_UPLOADED = "file_uploaded", "Загрузка файла"
    FILE_DELETED = "file_deleted", "Удаление файла"
    COMMENT_ADDED = "comment_added", "Добавление комментария"
    COMMENT_UPDATED = "comment_updated", "Редактирование комментария"
    COMMENT_DELETED = "comment_deleted", "Удаление комментария"
    SUBMITTED = "submitted", "Отправка на согласование"
    APPROVED = "approved", "Согласование"
    RETURNED = "returned", "Возврат"
    RESUBMITTED = "resubmitted", "Повторная отправка"
    REGISTERED = "registered", "Регистрация"
    COMPLETED = "completed", "Завершение"
    ARCHIVED = "archived", "Архивирование"
    RESTORED = "restored", "Восстановление"


class DocumentHistory(UUIDModel):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="history",
        verbose_name="Документ",
    )
    user = models.ForeignKey(
        "accounts.User",
        null=True,
        on_delete=models.SET_NULL,
        related_name="document_history_entries",
        verbose_name="Пользователь",
    )
    action = models.CharField(
        "Действие", max_length=30, choices=DocumentHistoryAction.choices, db_index=True
    )
    old_values = models.JSONField("Старые значения", default=dict, blank=True)
    new_values = models.JSONField("Новые значения", default=dict, blank=True)
    description = models.TextField("Описание", blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "История документа"
        verbose_name_plural = "История документов"
        indexes = [models.Index(fields=["document", "created_at"])]

    def __str__(self):
        return f"{self.document}: {self.action}"

    def save(self, *args, **kwargs):
        if self.pk and DocumentHistory.objects.filter(pk=self.pk).exists():
            raise ValueError("Записи истории документа нельзя изменять")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Записи истории документа нельзя удалять")
