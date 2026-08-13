# Authentication — E-SU

Аутентификация построена на JWT (`djangorestframework-simplejwt`). Выбран **один**
способ передачи токена — HTTP-заголовок `Authorization: Bearer <access>`.
httpOnly-cookies не используются; два способа не смешиваются.

Все эндпоинты — под версией `/api/v1/`.

---

## Эндпоинты

| Method | Endpoint | Назначение | Доступ |
|---|---|---|---|
| POST | `/api/v1/auth/login/` | Вход по email + пароль | публичный |
| POST | `/api/v1/auth/refresh/` | Обновление access-токена | публичный (по refresh) |
| POST | `/api/v1/auth/logout/` | Выход, отзыв refresh-токена | авторизован |
| GET·PATCH | `/api/v1/auth/me/` | Профиль текущего пользователя | авторизован |
| POST | `/api/v1/auth/change-password/` | Смена своего пароля | авторизован |
| POST | `/api/v1/auth/forgot-password/` | Запрос ссылки на сброс | публичный |
| POST | `/api/v1/auth/reset-password/` | Установка нового пароля по ссылке | публичный |

---

## Поток входа

**Запрос:**

```json
POST /api/v1/auth/login/
{ "email": "employee@esu.kg", "password": "Demo123!" }
```

**Ответ** (`data`): `access`, `refresh` и объект `user` с ролью и `permissions`:

```json
{
  "data": {
    "access": "…",
    "refresh": "…",
    "user": {
      "id": "uuid", "email": "employee@esu.kg", "full_name": "Иванов Иван",
      "role": { "code": "employee", "name": "Сотрудник" },
      "permissions": ["documents.view", "documents.create"],
      "status": "active"
    }
  },
  "message": "Success"
}
```

Дальше каждый запрос к защищённым эндпоинтам:

```
Authorization: Bearer <access>
```

---

## Токены

| Токен | Время жизни (по умолчанию) | Настройка |
|---|---|---|
| access | 30 минут | `ACCESS_TOKEN_LIFETIME_MINUTES` |
| refresh | 7 дней | `REFRESH_TOKEN_LIFETIME_DAYS` |

- **Ротация:** при вызове `/auth/refresh/` выдаётся новая пара, а **старый refresh
  заносится в blacklist** (`ROTATE_REFRESH_TOKENS=True`, `BLACKLIST_AFTER_ROTATION=True`).
  Повторное использование старого refresh → `401`.
- **Logout** заносит переданный refresh в blacklist — по нему больше нельзя получить
  access. Logout идемпотентен: недействительный токен тоже возвращает `204`.

---

## Проверки доступа

- **Неверные email/пароль** → `401`.
- **Неактивный / заблокированный / уволенный пользователь не входит:** login проверяет
  статус (`active`), а `JWTAuthentication` отклоняет пользователя с `is_active=False`.
  Поэтому после блокировки access-токен перестаёт работать немедленно.
- Пароль **не появляется** в ответах и в логах: сериализаторы не отдают пароль, а поля
  паролей помечены `write_only`; в аудит пароли не пишутся.

---

## Восстановление пароля

1. `POST /auth/forgot-password/ {email}` — ответ всегда одинаковый, независимо от того,
   существует ли аккаунт (защита от перебора email).
2. На email отправляется ссылка `FRONTEND_RESET_PASSWORD_URL?uid=…&token=…`.
3. `POST /auth/reset-password/ {uid, token, new_password}` — устанавливает пароль.

Свойства reset-токена (Django `default_token_generator`):

- **Одноразовый** — после смены пароля токен становится недействительным (повторное
  использование → `400`).
- **Ограничен по времени** — `PASSWORD_RESET_TIMEOUT` = 24 часа.
- Новый пароль проходит валидацию (`AUTH_PASSWORD_VALIDATORS`).

---

## Throttling

Ограничения (scope-throttling DRF), продакшн-значения:

| Scope | Эндпоинты | Лимит |
|---|---|---|
| `login` | `/auth/login/` | 10/min |
| `password_reset` | `/auth/forgot-password/`, `/auth/reset-password/` | 5/hour |

Превышение лимита → `429`. В `development` лимиты подняты, чтобы не мешать отладке.

---

## Аудит аутентификации

В журнал (`/api/v1/audit/`) пишутся: `login success`, `login failure` (без пароля),
`logout`, `password reset request`, `password reset`, `password change`. Пароли, JWT,
refresh/reset токены, `SECRET_KEY` и cookies в аудит **не** сохраняются.
