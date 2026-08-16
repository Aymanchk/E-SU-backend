"""Единый формат ошибок API."""

import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


class StructuredAPIException(exceptions.APIException):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, *, code: str, message: str, details=None):
        self.error_code = code
        self.error_message = message
        self.error_details = details or {}
        super().__init__(detail=message, code=code)


ERROR_CODES = {
    status.HTTP_400_BAD_REQUEST: "validation_error",
    status.HTTP_401_UNAUTHORIZED: "not_authenticated",
    status.HTTP_403_FORBIDDEN: "permission_denied",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "unsupported_media_type",
    status.HTTP_429_TOO_MANY_REQUESTS: "throttled",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "server_error",
}

DEFAULT_MESSAGES = {
    status.HTTP_400_BAD_REQUEST: "Некорректные данные",
    status.HTTP_401_UNAUTHORIZED: "Требуется авторизация",
    status.HTTP_403_FORBIDDEN: "Недостаточно прав",
    status.HTTP_404_NOT_FOUND: "Объект не найден",
    status.HTTP_405_METHOD_NOT_ALLOWED: "Метод не поддерживается",
    status.HTTP_409_CONFLICT: "Конфликт данных",
    status.HTTP_429_TOO_MANY_REQUESTS: "Слишком много запросов",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "Внутренняя ошибка сервера",
}


def build_error_response(code, message, details=None, http_status=400, headers=None):
    return Response(
        {
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            }
        },
        status=http_status,
        headers=headers,
    )


def custom_exception_handler(exc, context):
    # Приводим исключения Django к исключениям DRF
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()
    elif isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(
            exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        )
    elif isinstance(exc, IntegrityError):
        logger.warning("IntegrityError: %s", exc)
        return build_error_response(
            code="conflict",
            message="Нарушено ограничение целостности данных",
            http_status=status.HTTP_409_CONFLICT,
        )

    response = drf_exception_handler(exc, context)

    # None означает необработанное исключение, его пропускаем дальше,
    # Django вернёт 500 и залогирует трейсбек
    if response is None:
        return None

    if isinstance(exc, StructuredAPIException):
        return build_error_response(
            code=exc.error_code,
            message=exc.error_message,
            details=exc.error_details,
            http_status=exc.status_code,
            headers=getattr(response, "headers", None),
        )

    http_status = response.status_code
    code = ERROR_CODES.get(http_status, "error")
    message = DEFAULT_MESSAGES.get(http_status, "Ошибка запроса")
    details = {}

    data = response.data

    if isinstance(data, dict):
        if "detail" in data:
            message = str(data["detail"])
            code = getattr(data["detail"], "code", code) or code
        else:
            details = data
    elif isinstance(data, list):
        if len(data) == 1 and isinstance(data[0], str):
            message = data[0]
        else:
            details = {"non_field_errors": data}

    # У ValidationError с одним общим сообщением показываем его в message
    if (
        http_status == status.HTTP_400_BAD_REQUEST
        and isinstance(details, dict)
        and list(details.keys()) == ["non_field_errors"]
        and len(details["non_field_errors"]) == 1
    ):
        message = str(details["non_field_errors"][0])
        details = {}

    return build_error_response(
        code=code,
        message=message,
        details=details,
        http_status=http_status,
        headers=getattr(response, "headers", None),
    )
