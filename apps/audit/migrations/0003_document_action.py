from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("audit", "0002_document_register_action")]

    operations = [
        migrations.AlterField(
            model_name="auditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("login", "Вход в систему"),
                    ("logout", "Выход из системы"),
                    ("login_failed", "Неудачная попытка входа"),
                    ("password_change", "Смена пароля"),
                    ("password_reset_request", "Запрос восстановления пароля"),
                    ("password_reset", "Восстановление пароля"),
                    ("profile_update", "Изменение своего профиля"),
                    ("user_create", "Создание пользователя"),
                    ("user_update", "Изменение пользователя"),
                    ("user_delete", "Удаление пользователя"),
                    ("user_block", "Блокировка пользователя"),
                    ("user_activate", "Активация пользователя"),
                    ("user_reset_password", "Сброс пароля пользователя"),
                    ("user_role_change", "Изменение роли пользователя"),
                    ("role_create", "Создание роли"),
                    ("role_update", "Изменение роли"),
                    ("role_delete", "Удаление роли"),
                    ("role_permissions_update", "Изменение прав роли"),
                    ("department_create", "Создание подразделения"),
                    ("department_update", "Изменение подразделения"),
                    ("department_delete", "Удаление подразделения"),
                    ("settings_update", "Изменение системных настроек"),
                    ("document_action", "Действие с документом"),
                    ("document_register", "Регистрация документа"),
                ],
                db_index=True,
                max_length=100,
                verbose_name="Действие",
            ),
        )
    ]
