from django.db import models

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
