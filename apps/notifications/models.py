from django.db import models

from apps.common.models import UUIDModel


class NotificationType(models.TextChoices):
    DOCUMENT_SUBMITTED = "document_submitted", "Документ отправлен"
    APPROVAL_REQUIRED = "approval_required", "Требуется согласование"
    DOCUMENT_APPROVED = "document_approved", "Документ согласован"
    DOCUMENT_RETURNED = "document_returned", "Документ возвращён"
    DEADLINE_APPROACHING = "deadline_approaching", "Приближается дедлайн"
    DOCUMENT_OVERDUE = "document_overdue", "Документ просрочен"
    RESPONSIBLE_ASSIGNED = "responsible_assigned", "Назначен ответственный"
    COMMENT_ADDED = "comment_added", "Добавлен комментарий"
    DOCUMENT_REGISTERED = "document_registered", "Документ зарегистрирован"
    DOCUMENT_ARCHIVED = "document_archived", "Документ архивирован"


class Notification(UUIDModel):
    recipient = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Получатель",
    )
    type = models.CharField("Тип", max_length=40, choices=NotificationType.choices, db_index=True)
    title = models.CharField("Заголовок", max_length=255)
    message = models.TextField("Сообщение")
    document = models.ForeignKey(
        "documents.Document",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Документ",
    )
    is_read = models.BooleanField("Прочитано", default=False, db_index=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True, db_index=True)
    read_at = models.DateTimeField("Прочитано", null=True, blank=True)
    dedupe_key = models.CharField(
        "Ключ дедупликации",
        max_length=255,
        null=True,
        blank=True,
        unique=True,
        editable=False,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        indexes = [models.Index(fields=["recipient", "is_read", "created_at"])]

    def __str__(self):
        return f"{self.recipient}: {self.title}"
