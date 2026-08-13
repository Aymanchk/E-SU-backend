"""Сервисные функции приложения accounts."""

from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)


def blacklist_user_refresh_tokens(user):
    """
    Заносит все активные refresh-токены пользователя в чёрный список.

    Используется при смене/сбросе пароля и блокировке — после этого старые
    refresh-токены становятся недействительными (ТЗ §5, §7).
    """
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)
