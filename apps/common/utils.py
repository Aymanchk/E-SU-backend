"""Мелкие вспомогательные функции."""

import re
import secrets
import string


def get_client_ip(request):
    """Определяет IP клиента с учётом прокси."""
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def get_user_agent(request):
    if request is None:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")[:500]


def generate_password(length=12):
    """Генерирует пароль, который пройдёт валидаторы Django."""
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
        ):
            return password


def normalize_phone(value):
    """Приводит телефон к формату +996XXXXXXXXX."""
    if not value:
        return ""
    digits = re.sub(r"\D", "", value)
    if digits.startswith("996"):
        return f"+{digits}"
    if digits.startswith("0") and len(digits) == 10:
        return f"+996{digits[1:]}"
    return f"+{digits}" if digits else ""
