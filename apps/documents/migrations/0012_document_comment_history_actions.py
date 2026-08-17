from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("documents", "0011_department_number_counter")]

    operations = [
        migrations.AlterField(
            model_name="documenthistory",
            name="action",
            field=models.CharField(
                choices=[
                    ("created", "Создание"),
                    ("updated", "Редактирование"),
                    ("file_uploaded", "Загрузка файла"),
                    ("file_deleted", "Удаление файла"),
                    ("comment_added", "Добавление комментария"),
                    ("comment_updated", "Редактирование комментария"),
                    ("comment_deleted", "Удаление комментария"),
                    ("submitted", "Отправка на согласование"),
                    ("approved", "Согласование"),
                    ("returned", "Возврат"),
                    ("resubmitted", "Повторная отправка"),
                    ("registered", "Регистрация"),
                    ("completed", "Завершение"),
                    ("archived", "Архивирование"),
                    ("restored", "Восстановление"),
                ],
                db_index=True,
                max_length=30,
                verbose_name="Действие",
            ),
        )
    ]
