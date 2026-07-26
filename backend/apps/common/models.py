"""Абстрактные базовые модели проекта."""

import json
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class UUIDModel(models.Model):
    """Первичный ключ UUID вместо автоинкремента."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="ID",
    )

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    """Даты создания и изменения плюс кто это сделал."""

    created_at = models.DateTimeField("Создано", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("Изменено", auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_created",
        verbose_name="Создал",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_updated",
        verbose_name="Изменил",
    )

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet, у которого delete() не удаляет физически."""

    def delete(self):
        return self.update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager):
    """Менеджер, который по умолчанию скрывает удалённые записи."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)


class AllObjectsManager(models.Manager):
    """Менеджер, который видит всё, включая удалённое."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class SoftDeleteModel(models.Model):
    """Мягкое удаление."""

    is_deleted = models.BooleanField("Удалено", default=False, db_index=True)
    deleted_at = models.DateTimeField("Дата удаления", null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at"])

    def hard_delete(self, using=None, keep_parents=False):
        super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at"])


class SystemSetting(models.Model):
    """Системная настройка вида ключ-значение."""

    class ValueType(models.TextChoices):
        STRING = "string", "Строка"
        INTEGER = "integer", "Целое число"
        BOOLEAN = "boolean", "Да/Нет"
        JSON = "json", "JSON"

    key = models.CharField("Ключ", max_length=100, unique=True, db_index=True)
    value = models.TextField("Значение", blank=True)
    value_type = models.CharField(
        "Тип значения",
        max_length=20,
        choices=ValueType.choices,
        default=ValueType.STRING,
    )
    description = models.TextField("Описание", blank=True)
    is_public = models.BooleanField(
        "Доступна всем пользователям",
        default=False,
        help_text="Публичные настройки видит любой авторизованный пользователь",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_settings",
        verbose_name="Кто изменил",
    )
    updated_at = models.DateTimeField("Изменено", auto_now=True)

    class Meta:
        verbose_name = "Системная настройка"
        verbose_name_plural = "Системные настройки"
        ordering = ["key"]

    def __str__(self):
        return self.key

    def get_value(self):
        """Приводит строку к нужному типу Python."""
        if self.value_type == self.ValueType.INTEGER:
            try:
                return int(self.value)
            except (TypeError, ValueError):
                return 0
        if self.value_type == self.ValueType.BOOLEAN:
            return str(self.value).lower() in ("true", "1", "yes", "да")
        if self.value_type == self.ValueType.JSON:
            try:
                return json.loads(self.value or "{}")
            except json.JSONDecodeError:
                return {}
        return self.value

    def set_value(self, raw):
        """Записывает значение Python в строку."""
        if self.value_type == self.ValueType.JSON:
            self.value = json.dumps(raw, ensure_ascii=False)
        elif self.value_type == self.ValueType.BOOLEAN:
            self.value = "true" if raw else "false"
        else:
            self.value = str(raw)
