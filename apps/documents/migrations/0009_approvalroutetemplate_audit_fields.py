import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0008_approval_route_templates"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="approvalroutetemplate",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="%(app_label)s_%(class)s_created",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Создал",
            ),
        ),
        migrations.AddField(
            model_name="approvalroutetemplate",
            name="updated_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="%(app_label)s_%(class)s_updated",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Изменил",
            ),
        ),
        migrations.AlterField(
            model_name="approvalroutetemplate",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True, db_index=True, verbose_name="Создано"
            ),
        ),
        migrations.AlterField(
            model_name="approvalroutetemplate",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, verbose_name="Изменено"),
        ),
    ]
