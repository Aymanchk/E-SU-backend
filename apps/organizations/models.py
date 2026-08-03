"""Организационная структура."""

from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import SoftDeleteModel, TimeStampedModel, UUIDModel


class DepartmentStatus(models.TextChoices):
    ACTIVE = "active", "Активно"
    INACTIVE = "inactive", "Неактивно"


class Department(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """Подразделение университета. Поддерживает иерархию через parent."""

    name = models.CharField("Название", max_length=200, db_index=True)
    code = models.SlugField("Код", max_length=50, unique=True, db_index=True)
    description = models.TextField("Описание", blank=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
        verbose_name="Родительское подразделение",
    )
    manager = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_departments",
        verbose_name="Руководитель",
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=DepartmentStatus.choices,
        default=DepartmentStatus.ACTIVE,
        db_index=True,
    )

    class Meta:
        verbose_name = "Подразделение"
        verbose_name_plural = "Подразделения"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        parent = self.parent
        seen = set()
        while parent is not None:
            if parent.pk == self.pk:
                raise ValidationError({"parent": "Подразделение не может быть своим родителем"})
            if parent.pk in seen:
                break
            seen.add(parent.pk)
            parent = parent.parent

    @property
    def level(self):
        level = 0
        parent = self.parent
        while parent is not None:
            level += 1
            parent = parent.parent
        return level

    def get_ancestors(self):
        ancestors = []
        parent = self.parent
        while parent is not None:
            ancestors.append(parent)
            parent = parent.parent
        return list(reversed(ancestors))

    def get_descendants(self):
        result = []
        stack = list(self.children.all())
        while stack:
            node = stack.pop()
            result.append(node)
            stack.extend(node.children.all())
        return result
