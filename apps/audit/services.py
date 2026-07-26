"""Функции записи в журнал аудита."""

import logging

from apps.common.utils import get_client_ip, get_user_agent

from .constants import AuditResult
from .middleware import get_current_request
from .models import AuditLog

logger = logging.getLogger(__name__)


def log_action(
    request=None,
    *,
    user=None,
    action,
    obj=None,
    object_type=None,
    object_id=None,
    description="",
    result=AuditResult.SUCCESS,
    metadata=None,
):
    """
    Записывает действие в журнал.

    Ошибка записи не должна ронять основной запрос,
    поэтому всё обёрнуто в try/except.
    """
    try:
        if request is None:
            request = get_current_request()

        if user is None and request is not None:
            candidate = getattr(request, "user", None)
            if candidate is not None and candidate.is_authenticated:
                user = candidate

        if obj is not None:
            object_type = object_type or obj.__class__.__name__
            object_id = object_id or str(obj.pk)

        AuditLog.objects.create(
            user=user,
            action=action,
            object_type=object_type or "",
            object_id=object_id or "",
            description=description,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            result=result,
            metadata=metadata or {},
        )
    except Exception as exc:
        logger.error("Не удалось записать действие в журнал аудита: %s", exc)
