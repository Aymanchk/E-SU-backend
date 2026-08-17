from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("documents", "0012_document_comment_history_actions")]

    operations = [
        migrations.AddField(
            model_name="document",
            name="status_before_overdue",
            field=models.CharField(
                blank=True,
                choices=[
                    ("draft", "Черновик"),
                    ("in_review", "На согласовании"),
                    ("returned", "Возвращён"),
                    ("approved", "Согласован"),
                    ("completed", "Завершён"),
                    ("overdue", "Просрочен"),
                    ("archived", "В архиве"),
                ],
                editable=False,
                max_length=20,
                null=True,
                verbose_name="Статус до просрочки",
            ),
        )
    ]
