# E-SU Backend

Backend системы электронного документооборота Салымбеков Университета.

## Стек

- Python 3.12
- Django 5.0, Django REST Framework
- PostgreSQL 16
- Redis 7, Celery
- JWT (simplejwt)
- drf-spectacular (OpenAPI 3)
- Docker, docker compose
- pytest, ruff

## Требования

- Python 3.12+
- PostgreSQL 16+
- Redis 7+
- Docker и Docker Compose (для запуска в контейнерах)

## Быстрый старт через Docker

```bash
cp .env.docker.example .env.docker
# заполнить SECRET_KEY, DATABASE_URL, REDIS_URL (для compose — хосты db/redis)

docker compose up --build
docker compose exec web python manage.py createsuperuser
```

API доступен на http://localhost:8000

## Локальный запуск без Docker

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements/development.txt

cp .env.example .env
# заполнить переменные (для локального Postgres — хост localhost)

createdb esu
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Отдельным терминалом воркер Celery:

```bash
celery -A config worker -l info
```

## Команды

```bash
python manage.py migrate              # применить миграции
python manage.py makemigrations       # создать миграции
python manage.py createsuperuser      # создать администратора
python manage.py runserver            # запустить сервер разработки
python manage.py seed_demo            # наполнить демо-данными
python manage.py cleanup_audit --days 365   # очистить старый аудит
celery -A config worker -l info       # запустить воркер Celery
pytest                                # запустить тесты
pytest --cov=apps                     # тесты с покрытием
ruff check .                          # линтер
ruff format --check .                 # проверка форматирования
```

## Переменные окружения

| Переменная | Описание |
|---|---|
| DEBUG | Режим отладки |
| SECRET_KEY | Секретный ключ Django |
| DATABASE_URL | Строка подключения к PostgreSQL |
| REDIS_URL | Строка подключения к Redis |
| ALLOWED_HOSTS | Разрешённые хосты через запятую |
| CORS_ALLOWED_ORIGINS | Разрешённые источники для CORS |
| ACCESS_TOKEN_LIFETIME_MINUTES | Время жизни access токена |
| REFRESH_TOKEN_LIFETIME_DAYS | Время жизни refresh токена |
| EMAIL_HOST | SMTP сервер |
| EMAIL_PORT | Порт SMTP |
| EMAIL_HOST_USER | Пользователь SMTP |
| EMAIL_HOST_PASSWORD | Пароль SMTP |
| DEFAULT_FROM_EMAIL | Адрес отправителя |
| FRONTEND_RESET_PASSWORD_URL | Страница фронтенда для сброса пароля |

Файл `.env` не коммитится. Шаблон в `.env.example`.

**Важно:** `SECRET_KEY` не должен содержать символ `#` — `django-environ` обрывает
значение на нём даже внутри кавычек (проверено на практике). Безопасный способ
сгенерировать ключ: `python -c "import secrets; print(secrets.token_urlsafe(50))"`.

## Версионирование API

Основные эндпоинты подключены под префиксом `/api/v1/` (версия задаётся переменной
`API_VERSION`, по умолчанию `v1`). Старый префикс `/api/` временно сохранён ради
обратной совместимости; новый фронтенд должен использовать только `/api/v1/`.
Swagger отображает только версионированные эндпоинты.

## Документация API

- Swagger UI: http://localhost:8000/api/docs/
- ReDoc: http://localhost:8000/api/redoc/
- OpenAPI схема: http://localhost:8000/api/schema/
- Health-check: http://localhost:8000/api/health/

Контракт для frontend и справочники:

- [docs/FRONTEND_API_CONTRACT.md](docs/FRONTEND_API_CONTRACT.md) — таблица эндпоинтов
- [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md) — авторизация и токены
- [docs/PERMISSIONS.md](docs/PERMISSIONS.md) — роли и права

## Формат ответов

Успех:

```json
{"data": {}, "message": "Success"}
```

Ошибка:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Некорректные данные",
    "details": {"email": ["Обязательное поле."]}
  }
}
```

Список (внутри `data`):

```json
{"count": 100, "next": null, "previous": null, "results": []}
```

## Структура проекта

```
backend/
├── config/
│   ├── settings/       base, development, production
│   ├── urls.py
│   └── celery.py
├── apps/
│   ├── common/         базовые модели, формат ответов, настройки, health
│   ├── accounts/       пользователи, роли, права, авторизация
│   ├── organizations/  подразделения
│   └── audit/          журнал действий
├── requirements/
├── tests/
├── templates/emails/
├── Dockerfile
└── docker-compose.yml
```

## Роли и права

Базовые роли: `admin`, `manager`, `office`, `employee`.

Права:

| Код | Описание |
|---|---|
| documents.view | Просмотр документов |
| documents.create | Создание документов |
| documents.edit | Редактирование документов |
| documents.approve | Согласование документов |
| documents.return | Возврат на доработку |
| documents.archive | Архивирование |
| users.manage | Управление пользователями |
| departments.manage | Управление подразделениями |
| categories.manage | Управление категориями |
| audit.view | Просмотр журнала аудита |
| settings.manage | Управление настройками |

Роли и права создаются data-миграцией автоматически.

## Демо-данные

Команда `python manage.py seed_demo` идемпотентно создаёт демо-подразделения
(Ректорат, IT отдел, Бухгалтерия, Отдел кадров) и тестовых пользователей.

> **Только для development.** Не использовать в production.

| Email | Роль | Пароль |
|---|---|---|
| admin@esu.kg | admin | `DemoPass123!` |
| manager@esu.kg | manager | `DemoPass123!` |
| office@esu.kg | office | `DemoPass123!` |
| employee@esu.kg | employee | `DemoPass123!` |

## Работа с Git

- `main` стабильная версия, `develop` текущая разработка
- Прямые пуши в `main` и `develop` запрещены
- Ветки: `feature/ESU-123-task-name`, `fix/ESU-124-task-name`
- Коммиты: `feat:`, `fix:`, `refactor:`
- Одна задача ClickUp = одна ветка = один Pull Request
- Merge после ревью другим разработчиком
