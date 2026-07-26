"""Фоновые задачи приложения accounts."""

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _send(subject, template_name, context, to_email):
    """Отправка письма с текстовой и HTML версией."""
    text_body = render_to_string(f"emails/{template_name}.txt", context)
    html_body = render_to_string(f"emails/{template_name}.html", context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_email(self, email, full_name, reset_url):
    try:
        _send(
            subject="Восстановление пароля E-SU",
            template_name="password_reset",
            context={"full_name": full_name, "reset_url": reset_url},
            to_email=email,
        )
    except Exception as exc:
        logger.error("Ошибка отправки письма сброса пароля на %s: %s", email, exc)
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_account_created_email(self, email, full_name, password, login_url=None):
    try:
        _send(
            subject="Доступ к системе E-SU",
            template_name="account_created",
            context={
                "full_name": full_name,
                "email": email,
                "password": password,
                "login_url": login_url or settings.FRONTEND_URL,
            },
            to_email=email,
        )
    except Exception as exc:
        logger.error("Ошибка отправки письма о создании аккаунта %s: %s", email, exc)
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_account_blocked_email(self, email, full_name):
    try:
        _send(
            subject="Учётная запись E-SU заблокирована",
            template_name="account_blocked",
            context={"full_name": full_name},
            to_email=email,
        )
    except Exception as exc:
        logger.error("Ошибка отправки письма о блокировке %s: %s", email, exc)
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_changed_email(self, email, full_name):
    try:
        _send(
            subject="Пароль в системе E-SU изменён",
            template_name="password_changed",
            context={"full_name": full_name},
            to_email=email,
        )
    except Exception as exc:
        logger.error("Ошибка отправки письма о смене пароля %s: %s", email, exc)
        raise self.retry(exc=exc) from exc
