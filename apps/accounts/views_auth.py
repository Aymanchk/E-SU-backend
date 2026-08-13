"""Эндпоинты авторизации."""

import logging

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.audit.constants import AuditAction
from apps.audit.services import log_action

from .models import User, UserStatus
from .serializers import (
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    MeSerializer,
    ResetPasswordSerializer,
)
from .services import blacklist_user_refresh_tokens
from .tasks import send_password_changed_email, send_password_reset_email

logger = logging.getLogger(__name__)


def build_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


# ---------------------------------------------------------------------------


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "login"

    @extend_schema(
        summary="Вход в систему",
        description="Возвращает пару токенов и профиль пользователя.",
        tags=["Auth"],
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(description="Токены и профиль"),
            400: OpenApiResponse(description="Неверные данные или блокировка"),
            429: OpenApiResponse(description="Слишком много попыток входа"),
        },
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})

        if not serializer.is_valid():
            log_action(
                request,
                action=AuditAction.LOGIN_FAILED,
                result="failure",
                description=f"Неудачная попытка входа: {request.data.get('email', '')}",
                metadata={"email": request.data.get("email", "")},
            )
            raise serializers.ValidationError(serializer.errors)

        user = serializer.validated_data["user"]

        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        tokens = build_tokens(user)

        log_action(
            request,
            user=user,
            action=AuditAction.LOGIN,
            result="success",
            description="Вход в систему",
        )

        return Response(
            {
                **tokens,
                "user": MeSerializer(user, context={"request": request}).data,
            }
        )


class CustomTokenRefreshView(TokenRefreshView):
    """Обновление access токена. Ротация настроена в SIMPLE_JWT."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(summary="Обновление токена", tags=["Auth"])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Выход из системы",
        description="Заносит refresh токен в чёрный список.",
        tags=["Auth"],
        request={
            "application/json": {
                "type": "object",
                "properties": {"refresh": {"type": "string"}},
                "required": ["refresh"],
            }
        },
        responses={204: OpenApiResponse(description="Выход выполнен")},
    )
    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            raise serializers.ValidationError({"refresh": "Обязательное поле"})

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            # Токен уже недействителен, для клиента это всё равно успешный выход
            logger.info("Попытка logout с недействительным refresh токеном")

        log_action(
            request,
            action=AuditAction.LOGOUT,
            result="success",
            description="Выход из системы",
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Профиль текущего пользователя", tags=["Auth"], responses={200: MeSerializer}
    )
    def get(self, request):
        serializer = MeSerializer(request.user, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        summary="Редактирование своего профиля",
        tags=["Auth"],
        request=MeSerializer,
        responses={200: MeSerializer},
    )
    def patch(self, request):
        serializer = MeSerializer(
            request.user, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        log_action(
            request,
            action=AuditAction.PROFILE_UPDATE,
            obj=request.user,
            description="Изменение своего профиля",
            metadata={"fields": list(request.data.keys())},
        )

        return Response(serializer.data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Смена пароля",
        tags=["Auth"],
        request=ChangePasswordSerializer,
        responses={200: OpenApiResponse(description="Пароль изменён")},
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])

        # После смены пароля все старые refresh-токены недействительны (ТЗ §5).
        blacklist_user_refresh_tokens(user)

        send_password_changed_email.delay(user.email, user.full_name)

        log_action(
            request,
            action=AuditAction.PASSWORD_CHANGE,
            obj=user,
            description="Смена собственного пароля",
        )

        return Response({"message": "Пароль изменён"})


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "password_reset"

    @extend_schema(
        summary="Запрос восстановления пароля",
        description=(
            "Всегда возвращает одинаковый ответ, независимо от того, "
            "существует ли пользователь с таким email."
        ),
        tags=["Auth"],
        request=ForgotPasswordSerializer,
        responses={200: OpenApiResponse(description="Запрос принят")},
    )
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].lower().strip()
        user = User.objects.filter(email=email, is_active=True, status=UserStatus.ACTIVE).first()

        if user is not None:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = f"{settings.FRONTEND_RESET_PASSWORD_URL}?uid={uid}&token={token}"
            send_password_reset_email.delay(user.email, user.full_name, reset_url)

            log_action(
                request,
                user=user,
                action=AuditAction.PASSWORD_RESET_REQUEST,
                description="Запрошено восстановление пароля",
            )

        return Response({"message": "Если аккаунт с таким email существует, письмо отправлено"})


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "password_reset"

    @extend_schema(
        summary="Установка нового пароля",
        tags=["Auth"],
        request=ResetPasswordSerializer,
        responses={200: OpenApiResponse(description="Пароль обновлён")},
    )
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            user_pk = force_str(urlsafe_base64_decode(data["uid"]))
            user = User.objects.get(pk=user_pk)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError) as exc:
            raise serializers.ValidationError({"uid": "Ссылка недействительна"}) from exc

        if not default_token_generator.check_token(user, data["token"]):
            raise serializers.ValidationError(
                {"token": "Ссылка недействительна или срок её действия истёк"}
            )

        try:
            validate_password(data["new_password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)}) from exc

        user.set_password(data["new_password"])
        if user.status == UserStatus.INVITED:
            user.status = UserStatus.ACTIVE
        user.save(update_fields=["password", "status"])

        # После сброса пароля все старые refresh-токены недействительны (ТЗ §5).
        blacklist_user_refresh_tokens(user)

        log_action(
            request,
            user=user,
            action=AuditAction.PASSWORD_RESET,
            obj=user,
            description="Пароль восстановлен по ссылке из письма",
        )

        return Response({"message": "Пароль успешно изменён"})
