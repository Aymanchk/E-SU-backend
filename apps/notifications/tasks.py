import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from .models import Notification
from .services import DeadlineService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_notification_email(self, notification_id):
    try:
        notification = Notification.objects.select_related("recipient", "document").get(
            pk=notification_id
        )
        message = EmailMultiAlternatives(
            subject=f"E-SU: {notification.title}",
            body=notification.message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[notification.recipient.email],
        )
        message.attach_alternative(
            f"<h2>{notification.title}</h2><p>{notification.message}</p>", "text/html"
        )
        message.send(fail_silently=False)
    except Notification.DoesNotExist:
        logger.warning("Уведомление %s не найдено", notification_id)
    except Exception as exc:
        logger.error("Ошибка email-уведомления %s: %s", notification_id, exc)
        raise self.retry(exc=exc) from exc


@shared_task
def check_document_deadlines():
    return DeadlineService.check()
