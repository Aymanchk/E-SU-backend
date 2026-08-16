## Что сделано

Завершён backend документооборота E-SU и подготовлен контракт `/api/v1` для frontend.

## Основные endpoints

- Категории и шаблоны: `/api/v1/document-categories/`, `/api/v1/approval-route-templates/`
- Документы и списки: `/api/v1/documents/`, `/my/`, `/for-approval/`, `/returned/`, `/overdue/`, `/archive/`
- Workflow: `/submit/`, `/approval/`, `/approve/`, `/return/`, `/register/`, `/complete/`, `/archive/`, `/restore/`
- Файлы: `/files/`, `/api/v1/document-files/{id}/download/`, `/make-main/`
- Комментарии и история: `/comments/`, `/history/`
- Уведомления: `/api/v1/notifications/`, `/unread-count/`, `/read/`, `/read-all/`
- Dashboard: `/api/v1/dashboard/`

## Миграции документооборота

- `accounts.0003_seed_permissions_and_roles`
- `documents.0004_seed_document_register_permission`
- `documents.0005`–`0010`: файлы, согласование, история и шаблоны
- `documents.0011_department_number_counter`
- `documents.0012_document_comment_history_actions`
- `documents.0013_document_status_before_overdue`
- `documents.0014_document_performance_indexes`
- `audit.0002_document_register_action`
- `audit.0003_document_action`
- `notifications.0002_notification_contract_types`

## Проверки

- [x] Все миграции применяются на чистой PostgreSQL 16 базе
- [x] `python manage.py makemigrations --check --dry-run`
- [x] `python manage.py check`
- [x] OpenAPI schema validation
- [x] `ruff check .`
- [x] 270 тестов
- [x] Покрытие всего `apps`: 89.80% при обязательном пороге 85%
- [x] Конкурентная регистрация и конкурентное согласование проверены на PostgreSQL
- [x] Celery worker и Beat зарегистрировали deadline/cleanup задачи

## Документация

- `docs/FRONTEND_API_CONTRACT.md`
- Swagger UI: `/api/docs/`
- ReDoc: `/api/redoc/`
