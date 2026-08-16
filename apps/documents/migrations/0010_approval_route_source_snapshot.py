import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0009_approvalroutetemplate_audit_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="approvalroute",
            name="source",
            field=models.CharField(
                choices=[
                    ("manual", "Ручной маршрут"),
                    ("category_template", "Шаблон категории"),
                ],
                default="manual",
                max_length=30,
                verbose_name="Источник маршрута",
            ),
        ),
        migrations.AddField(
            model_name="approvalroute",
            name="template",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="approval_routes",
                to="documents.approvalroutetemplate",
                verbose_name="Исходный шаблон",
            ),
        ),
        migrations.AddField(
            model_name="approvalroute",
            name="template_snapshot",
            field=models.JSONField(
                blank=True, default=dict, verbose_name="Снимок шаблона"
            ),
        ),
    ]
