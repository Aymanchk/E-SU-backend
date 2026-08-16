"""Коды действий для журнала аудита."""

from django.db import models


class AuditAction(models.TextChoices):
    # Авторизация
    LOGIN = "login", "Вход в систему"
    LOGOUT = "logout", "Выход из системы"
    LOGIN_FAILED = "login_failed", "Неудачная попытка входа"

    # Пароли
    PASSWORD_CHANGE = "password_change", "Смена пароля"
    PASSWORD_RESET_REQUEST = "password_reset_request", "Запрос восстановления пароля"
    PASSWORD_RESET = "password_reset", "Восстановление пароля"

    # Профиль
    PROFILE_UPDATE = "profile_update", "Изменение своего профиля"

    # Пользователи
    USER_CREATE = "user_create", "Создание пользователя"
    USER_UPDATE = "user_update", "Изменение пользователя"
    USER_DELETE = "user_delete", "Удаление пользователя"
    USER_BLOCK = "user_block", "Блокировка пользователя"
    USER_ACTIVATE = "user_activate", "Активация пользователя"
    USER_RESET_PASSWORD = "user_reset_password", "Сброс пароля пользователя"
    USER_ROLE_CHANGE = "user_role_change", "Изменение роли пользователя"

    # Роли и права
    ROLE_CREATE = "role_create", "Создание роли"
    ROLE_UPDATE = "role_update", "Изменение роли"
    ROLE_DELETE = "role_delete", "Удаление роли"
    ROLE_PERMISSIONS_UPDATE = "role_permissions_update", "Изменение прав роли"

    # Подразделения
    DEPARTMENT_CREATE = "department_create", "Создание подразделения"
    DEPARTMENT_UPDATE = "department_update", "Изменение подразделения"
    DEPARTMENT_DELETE = "department_delete", "Удаление подразделения"

    # Настройки
    SETTINGS_UPDATE = "settings_update", "Изменение системных настроек"

    # Документы
    DOCUMENT_REGISTER = "document_register", "Регистрация документа"


class AuditResult(models.TextChoices):
    SUCCESS = "success", "Успешно"
    FAILURE = "failure", "Ошибка"
