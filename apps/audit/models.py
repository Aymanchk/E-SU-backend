"""Журнал аудита действий пользователей."""

import uuid

from django.conf import settings
from django.db import models

from .constants import AuditAction, AuditResult


class AuditLog(models.Model):
    """
    Запись журнала. Только на запись и чтение.
    Изменение и удаление через API запрещены.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
        verbose_name="Пользователь",
    )
    action = models.CharField(
        "Действие",
        max_length=100,
        choices=AuditAction.choices,
        db_index=True,
    )
    object_type = models.CharField("Тип объекта", max_length=100, blank=True, db_index=True)
    object_id = models.CharField("ID объекта", max_length=100, blank=True, db_index=True)
    description = models.TextField("Описание", blank=True)
    ip_address = models.GenericIPAddressField("IP-адрес", null=True, blank=True)
    user_agent = models.TextField("User-Agent", blank=True)
    result = models.CharField(
        "Результат",
        max_length=20,
        choices=AuditResult.choices,
        default=AuditResult.SUCCESS,
        db_index=True,
    )
    metadata = models.JSONField("Дополнительные данные", default=dict, blank=True)
    created_at = models.DateTimeField("Дата", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Запись журнала"
        verbose_name_plural = "Журнал аудита"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
            models.Index(fields=["object_type", "object_id"]),
        ]

    def __str__(self):
        who = self.user.email if self.user_id else "система"
        return f"{self.created_at:%Y-%m-%d %H:%M} {who} {self.action}"

    def save(self, *args, **kwargs):
        # Запись журнала нельзя изменить после создания
        if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
            raise ValueError("Записи журнала аудита нельзя изменять")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Записи журнала аудита нельзя удалять")
