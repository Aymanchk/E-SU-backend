from django.db import migrations, models


def rename_deadline_type(apps, schema_editor):
    Notification = apps.get_model("notifications", "Notification")
    Notification.objects.filter(type="deadline_soon").update(
        type="deadline_approaching"
    )


def restore_deadline_type(apps, schema_editor):
    Notification = apps.get_model("notifications", "Notification")
    Notification.objects.filter(type="deadline_approaching").update(
        type="deadline_soon"
    )


class Migration(migrations.Migration):
    dependencies = [("notifications", "0001_initial")]

    operations = [
        migrations.RunPython(rename_deadline_type, restore_deadline_type),
        migrations.AlterField(
            model_name="notification",
            name="type",
            field=models.CharField(
                choices=[
                    ("document_submitted", "Документ отправлен"),
                    ("approval_required", "Требуется согласование"),
                    ("document_approved", "Документ согласован"),
                    ("document_returned", "Документ возвращён"),
                    ("deadline_approaching", "Приближается дедлайн"),
                    ("document_overdue", "Документ просрочен"),
                    ("responsible_assigned", "Назначен ответственный"),
                    ("comment_added", "Добавлен комментарий"),
                    ("document_registered", "Документ зарегистрирован"),
                    ("document_archived", "Документ архивирован"),
                ],
                db_index=True,
                max_length=40,
                verbose_name="Тип",
            ),
        ),
    ]
