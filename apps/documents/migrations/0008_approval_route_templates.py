import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0007_documentcomment_documenthistory"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="documentcategory",
            name="requires_file",
            field=models.BooleanField(default=False, verbose_name="Обязательный файл"),
        ),
        migrations.CreateModel(
            name="ApprovalRouteTemplate",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200, verbose_name="Название")),
                (
                    "is_active",
                    models.BooleanField(db_index=True, default=True, verbose_name="Активен"),
                ),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approval_route_templates",
                        to="documents.documentcategory",
                        verbose_name="Категория",
                    ),
                ),
            ],
            options={
                "verbose_name": "Шаблон маршрута согласования",
                "verbose_name_plural": "Шаблоны маршрутов согласования",
                "ordering": ["category", "name"],
            },
        ),
        migrations.CreateModel(
            name="ApprovalRouteTemplateStep",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("order", models.PositiveIntegerField(verbose_name="Порядок")),
                (
                    "approver_type",
                    models.CharField(
                        choices=[
                            ("specific_user", "Конкретный пользователь"),
                            ("role", "Роль"),
                            ("department_manager", "Руководитель подразделения"),
                            ("document_responsible", "Ответственный за документ"),
                        ],
                        max_length=30,
                        verbose_name="Тип согласующего",
                    ),
                ),
                (
                    "department_relation",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("author_department", "Подразделение автора"),
                            ("document_department", "Подразделение документа"),
                        ],
                        max_length=30,
                        verbose_name="Связь с подразделением",
                    ),
                ),
                (
                    "is_required",
                    models.BooleanField(default=True, verbose_name="Обязательный шаг"),
                ),
                (
                    "role",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="approval_template_steps",
                        to="accounts.role",
                        verbose_name="Роль",
                    ),
                ),
                (
                    "specific_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="approval_template_steps",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Конкретный пользователь",
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="steps",
                        to="documents.approvalroutetemplate",
                        verbose_name="Шаблон",
                    ),
                ),
            ],
            options={
                "verbose_name": "Шаг шаблона согласования",
                "verbose_name_plural": "Шаги шаблона согласования",
                "ordering": ["order"],
            },
        ),
        migrations.AddConstraint(
            model_name="approvalroutetemplate",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_active", True)),
                fields=("category",),
                name="unique_active_route_template_category",
            ),
        ),
        migrations.AddConstraint(
            model_name="approvalroutetemplatestep",
            constraint=models.UniqueConstraint(
                fields=("template", "order"),
                name="unique_route_template_step_order",
            ),
        ),
    ]
