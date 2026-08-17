<<<<<<< HEAD
# Frontend API Contract — E-SU

Контракт между backend и frontend E-SU. Все основные эндпоинты подключены под
версионированным префиксом **`/api/v1/`**. Старый префикс `/api/` временно сохранён
ради обратной совместимости, но новый фронтенд должен использовать только `/api/v1/`.

- Swagger UI: `/api/docs/`
- OpenAPI схема: `/api/schema/`
- Аутентификация: см. [AUTHENTICATION.md](AUTHENTICATION.md)
- Права и роли: см. [PERMISSIONS.md](PERMISSIONS.md)

---

## Единый формат ответов

**Успешный одиночный ответ:**

```json
{ "data": { }, "message": "Success" }
```

**Успешный список** (пагинация внутри `data`):

```json
{
  "data": { "count": 100, "next": null, "previous": null, "results": [] },
=======
# E-SU Frontend API Contract

Актуальный контракт backend документооборота. Канонический префикс: `/api/v1`.
Маршруты без `/v1` временно оставлены для совместимости и не должны использоваться новым frontend.

Интерактивная документация локально:

- Swagger UI: `/api/docs/`
- ReDoc: `/api/redoc/`
- OpenAPI schema: `/api/schema/`

## Общие правила

Все защищённые запросы используют JWT:

```http
Authorization: Bearer <access_token>
```

Успешный JSON-ответ:

```json
{
  "data": {},
>>>>>>> 62d5b43 (docs: add frontend api contract)
  "message": "Success"
}
```

<<<<<<< HEAD
**Ошибка:**
=======
Ошибка:
>>>>>>> 62d5b43 (docs: add frontend api contract)

```json
{
  "error": {
    "code": "validation_error",
    "message": "Некорректные данные",
<<<<<<< HEAD
    "details": { "email": ["Обязательное поле."] }
=======
    "details": {
      "title": ["Обязательное поле."]
    }
>>>>>>> 62d5b43 (docs: add frontend api contract)
  }
}
```

<<<<<<< HEAD
**Коды ошибок** обрабатываются единообразно: `400, 401, 403, 404, 405, 409, 413, 429, 500`.
Traceback в production не возвращается.

**Пагинация:** параметры `page` и `page_size` (по умолчанию 20).

---

## Таблица эндпоинтов

| Frontend screen | Method | Endpoint | Request | Response | Filters | Permissions | Errors |
|---|---|---|---|---|---|---|---|
| **Login** | POST | `/api/v1/auth/login/` | `{email, password}` | `{user, access, refresh}` | — | публичный | 400, 401, 429 |
| Login (refresh) | POST | `/api/v1/auth/refresh/` | `{refresh}` | `{access, refresh}` | — | публичный | 401 |
| Logout | POST | `/api/v1/auth/logout/` | `{refresh}` | `204` | — | авторизован | 400 |
| Профиль | GET | `/api/v1/auth/me/` | — | профиль + `role` + `permissions` | — | авторизован | 401 |
| Профиль | PATCH | `/api/v1/auth/me/` | `{first_name, last_name, phone, …}` | обновлённый профиль | — | авторизован | 400 |
| Смена пароля | POST | `/api/v1/auth/change-password/` | `{old_password, new_password}` | `{message}` | — | авторизован | 400 |
| Забыли пароль | POST | `/api/v1/auth/forgot-password/` | `{email}` | `{message}` | — | публичный | 400, 429 |
| Сброс пароля | POST | `/api/v1/auth/reset-password/` | `{uid, token, new_password}` | `{message}` | — | публичный | 400, 429 |
| **Dashboard** | GET | `/api/v1/dashboard/` | — | сводка по роли (счётчики, списки) | — | авторизован | 401 |
| **Users** | GET | `/api/v1/users/` | — | список пользователей | `search, role, department, status, manager, is_active, ordering, page, page_size` | `users.manage` | 401, 403 |
| Users | POST | `/api/v1/users/` | `{email, first_name, last_name, phone, position, department_id, manager_id, role_id, status, temporary_password}` | созданный пользователь (без пароля) | — | `users.manage` | 400, 403, 409 |
| Users | GET | `/api/v1/users/{id}/` | — | пользователь | — | `users.manage` | 403, 404 |
| Users | PATCH | `/api/v1/users/{id}/` | частичное обновление | пользователь | — | `users.manage` | 400, 403, 404 |
| Users | POST | `/api/v1/users/{id}/activate/` | — | пользователь | — | `users.manage` | 403, 404 |
| Users | POST | `/api/v1/users/{id}/block/` | — | пользователь | — | `users.manage` | 400, 403, 404 |
| Users | POST | `/api/v1/users/{id}/reset-password/` | — | `{temporary_password?}` | — | `users.manage` | 403, 404 |
| **Departments** | GET | `/api/v1/departments/` | — | список подразделений | `search, name, code, status, manager, parent, root_only, ordering` | авторизован (чтение) | 401 |
| Departments | POST | `/api/v1/departments/` | `{name, code, parent, manager, …}` | подразделение | — | `departments.manage` | 400, 403, 409 |
| Departments | GET/PATCH/DELETE | `/api/v1/departments/{id}/` | — / patch | подразделение | — | `departments.manage` | 400, 403, 404, 409 |
| Departments | POST | `/api/v1/departments/{id}/activate/` · `/deactivate/` | — | подразделение | — | `departments.manage` | 403, 404 |
| Departments | GET | `/api/v1/departments/{id}/employees/` | — | сотрудники подразделения | `include_children` | авторизован | 404 |
| Departments | GET | `/api/v1/departments/tree/` | — | дерево подразделений | — | авторизован | — |
| **Categories** | GET | `/api/v1/document-categories/` | — | список категорий | `search, name, code, status, department, ordering` | авторизован (чтение) | 401 |
| Categories | POST/PATCH/DELETE | `/api/v1/document-categories/{id}/` | — | категория | — | `categories.manage` | 400, 403, 404 |
| Categories | POST | `/api/v1/document-categories/{id}/activate/` · `/deactivate/` | — | категория | — | `categories.manage` | 403, 404 |
| **Documents** | GET | `/api/v1/documents/` | — | список документов (по правам доступа) | `search, status, category, author, department, responsible, priority, created_from/to, deadline_from/to, ordering` | `documents.view` | 401, 403 |
| Documents | POST | `/api/v1/documents/` | `{title, category_id, …}` | документ | — | `documents.create` | 400, 403 |
| Documents | GET/PATCH/DELETE | `/api/v1/documents/{id}/` | — | документ | — | по доступу | 403, 404 |
| Documents | GET | `/api/v1/documents/my/` · `/returned/` · `/overdue/` · `/for-approval/` | — | подсписки | как список | `documents.view` | 401 |
| **Approval** | POST | `/api/v1/documents/{id}/submit/` | — | документ | — | автор | 400, 403, 404 |
| Approval | POST | `/api/v1/documents/{id}/approve/` | `{comment?}` | документ | — | `documents.approve` | 400, 403, 404 |
| Approval | POST | `/api/v1/documents/{id}/return/` | `{comment}` | документ | — | `documents.return` | 400, 403, 404 |
| Approval | GET | `/api/v1/documents/{id}/approval/` | — | маршрут согласования | — | по доступу | 404 |
| Approval | POST | `/api/v1/documents/{id}/register/` | — | документ + номер | — | `office` / register | 400, 403 |
| Approval | POST | `/api/v1/documents/{id}/archive/` · `/restore/` | — | документ | — | `documents.archive` | 403, 404 |
| Approval | GET/POST | `/api/v1/documents/{id}/comments/` | `{text}` | комментарий(ы) | — | по доступу | 403, 404 |
| Approval | GET | `/api/v1/documents/{id}/history/` | — | история изменений | — | по доступу | 404 |
| Approval | GET/POST | `/api/v1/documents/{id}/files/` | multipart | файл(ы) | — | по доступу | 403, 404, 413 |
| **Notifications** | GET | `/api/v1/notifications/` | — | список уведомлений | `ordering, page, page_size` | авторизован (свои) | 401 |
| Notifications | GET | `/api/v1/notifications/unread-count/` | — | `{count}` | — | авторизован | 401 |
| Notifications | POST | `/api/v1/notifications/{id}/read/` | — | уведомление | — | авторизован | 404 |
| Notifications | POST | `/api/v1/notifications/read-all/` | — | `{updated}` | — | авторизован | 401 |
| **Audit** | GET | `/api/v1/audit/` | — | журнал (read-only) | `user, role, action, object_type, object_id, document, department, result, date_from, date_to, search, ordering` | `audit.view` | 401, 403 |
| Audit | GET | `/api/v1/audit/{id}/` | — | запись журнала | — | `audit.view` | 403, 404 |
| **Settings** | GET | `/api/v1/settings/` | — | список настроек (приватные — только с правом) | — | авторизован (публичные) / `settings.manage` (все) | 401 |
| Settings | PATCH | `/api/v1/settings/` | `{key: value, …}` | обновлённый список | — | `settings.manage` | 400, 403 |

> `POST/PATCH/DELETE` для `/api/v1/audit/` **запрещены** — журнал только на чтение (405).

---

## Примечания для frontend

- **Права не вычисляются на фронте.** `permissions` приходят готовым списком в
  `GET /api/v1/auth/me/` и в ответе login. Роль — вспомогательное поле, не считайте
  права по названию роли.
- **Список permissions для таблицы-чекбоксов** отдаёт `GET /api/v1/permissions/`
  (сгруппирован по `group`). Подробнее — [PERMISSIONS.md](PERMISSIONS.md).
- Swagger содержит примеры request/response для основных операций.
=======
Основные коды: `validation_error`, `not_authenticated`, `permission_denied`,
`not_found`, `method_not_allowed`, `conflict`, `invalid_document_transition`.
Запрос чужого недоступного UUID возвращает `404` без раскрытия объекта.

Пагинация списков:

```json
{
  "data": {
    "count": 42,
    "next": "http://localhost:8000/api/v1/documents/?page=2",
    "previous": null,
    "results": []
  },
  "message": "Success"
}
```

Параметры: `page` и `page_size`; размер по умолчанию 20, максимум 100.

## Статусы документа

| Код | Значение |
|---|---|
| `draft` | Черновик |
| `in_review` | На согласовании |
| `returned` | Возвращён автору |
| `approved` | Согласован |
| `completed` | Завершён |
| `overdue` | Просрочен |
| `archived` | В архиве |

Основной workflow:

```text
draft -> in_review -> approved -> completed -> archived
            |                         ^           |
            -> returned -> in_review  |-----------|
```

`overdue` назначается фоновой задачей только разрешённым бизнес-статусам;
предыдущий статус хранится в `status_before_overdue`.

## Документы

### CRUD и списки

| Метод и endpoint | Permission | Допустимый статус / примечание |
|---|---|---|
| `GET /documents/` | `documents.view` | Только доступные пользователю объекты |
| `POST /documents/` | `documents.create` | Создаёт `draft`, автор берётся из JWT |
| `GET /documents/{id}/` | `documents.view` + object access | Любой видимый статус |
| `PATCH /documents/{id}/` | `documents.create` + автор/admin | Только `draft`, `returned` |
| `DELETE /documents/{id}/` | `documents.create` + автор/admin | Только `draft`, soft delete |
| `GET /documents/my/` | `documents.view` | Документы текущего автора |
| `GET /documents/for-approval/` | `documents.approve` | Только текущий шаг пользователя |
| `GET /documents/returned/` | `documents.view` | Возвращённые документы автора |
| `GET /documents/overdue/` | `documents.view` | Видимые просроченные документы |
| `GET /documents/archive/` | `documents.view` | Видимые архивные документы |

Создание и редактирование:

```json
{
  "title": "Приказ о назначении",
  "description": "Описание документа",
  "document_type": "order",
  "category_id": "8e17b9ef-8ff6-44e9-96aa-e0a672a57a8a",
  "department_id": "48d741a1-3ca9-4db9-bcbf-7405360f49dd",
  "responsible_id": "e3634ec5-2155-40f6-bff6-5bca8c77ff07",
  "priority": "normal",
  "deadline": "2026-08-20T12:00:00+06:00"
}
```

`category`, `department`, `responsible` временно принимаются как legacy aliases,
но frontend должен отправлять поля с суффиксом `_id`.
`registration_number`, `author`, `status` и служебные даты через PATCH не меняются.

Валидация:

- категория активна и разрешена подразделению;
- ответственный активен;
- deadline при создании находится в будущем;
- обычный пользователь создаёт документ только в своём подразделении;
- редактирование заблокировано во время и после согласования.

Фильтры всех основных и специальных списков:

- `search` — title, description, registration number;
- `status`, `category`, `department`, `author`, `responsible`, `priority`;
- `created_from`, `created_to`, `deadline_from`, `deadline_to` — ISO 8601;
- `ordering` — `created_at`, `updated_at`, `deadline`, `title`, `priority`,
  `status`, `registration_number`; префикс `-` задаёт обратный порядок;
- `page`, `page_size`.

Пример:

```http
GET /api/v1/documents/my/?status=draft&search=приказ&ordering=-created_at&page_size=20
```

### Workflow actions

| Метод и endpoint | Permission | Переход |
|---|---|---|
| `POST /documents/{id}/submit/` | `documents.create`, автор/admin | `draft/returned -> in_review` |
| `GET /documents/{id}/approval/` | `documents.view` | Текущий/последний маршрут |
| `POST /documents/{id}/approve/` | `documents.approve`, current approver | Следующий шаг или `approved` |
| `POST /documents/{id}/return/` | `documents.return`, current approver | `in_review -> returned` |
| `POST /documents/{id}/register/` | `documents.register` | Только `approved` |
| `POST /documents/{id}/complete/` | `documents.edit/create` + object rule | `approved -> completed` |
| `POST /documents/{id}/archive/` | `documents.archive` | `completed -> archived` |
| `POST /documents/{id}/restore/` | `documents.archive` | `archived -> completed` |

Ручной маршрут submit:

```json
{
  "approvers": [
    "82baa628-9085-40ec-a502-50d4c0473439",
    "a8346334-08bb-460c-8615-f8d9926ba39a"
  ]
}
```

Если `approvers` отсутствует или пуст, используется активный шаблон категории.
Ручной непустой список имеет приоритет. Повторы и неактивные пользователи запрещены.

Approve допускает необязательный комментарий:

```json
{"comment": "Согласовано"}
```

Return требует непустую причину:

```json
{"comment": "Исправьте реквизиты"}
```

Неверный переход возвращает:

```json
{
  "error": {
    "code": "invalid_document_transition",
    "message": "Документ нельзя архивировать из текущего статуса",
    "details": {
      "current_status": "draft",
      "requested_action": "archive"
    }
  }
}
```

## Файлы

| Метод и endpoint | Правило |
|---|---|
| `GET /documents/{id}/files/` | Object access к документу |
| `POST /documents/{id}/files/` | Автор/admin, только `draft/returned` |
| `GET /document-files/{id}/download/` | Object access, иначе `404` |
| `DELETE /document-files/{id}/` | Автор/admin, только `draft/returned` |
| `POST /document-files/{id}/make-main/` | Автор/admin, только `draft/returned` |

Upload использует только `multipart/form-data`:

```text
file: <binary>
is_main: true|false
```

Разрешены PDF, DOC, DOCX, XLSX, PNG, JPG/JPEG. Проверяются расширение, MIME,
сигнатура содержимого, непустой размер, лимит размера и количество файлов.
Имя в storage генерируется backend. Основной файл у документа только один.

## Комментарии и история

| Метод и endpoint | Правило |
|---|---|
| `GET /documents/{id}/comments/` | Только участники с object access |
| `POST /documents/{id}/comments/` | Object access; архив read-only |
| `PATCH /comments/{id}/` | Только автор обычного комментария |
| `DELETE /comments/{id}/` | Только автор обычного комментария |
| `GET /documents/{id}/history/` | Object access, строго read-only |

Создание комментария:

```json
{"text": "Комментарий к документу"}
```

`author` и `comment_type` задаёт backend. Служебные approval/return/system
комментарии неизменяемы. История возвращается хронологически и содержит actor,
action, description, old/new values и created_at.

## Категории и шаблоны маршрутов

Категории: `/document-categories/`, CRUD плюс `/{id}/activate/` и
`/{id}/deactivate/`. Изменения требуют `categories.manage`.

Шаблоны: `/approval-route-templates/`. Поддерживаются `specific_user`, `role`,
`department_manager`, `document_responsible`. Активный шаблон категории один;
созданный маршрут хранит неизменяемый snapshot.

## Уведомления

- `GET /notifications/`
- `GET /notifications/unread-count/`
- `POST /notifications/{id}/read/`
- `POST /notifications/read-all/`

Доступны только уведомления текущего пользователя. Фильтры списка: `type`,
`is_read`, `document`; ordering — `created_at`.

Типы: `document_submitted`, `document_approved`, `document_returned`,
`deadline_approaching`, `document_overdue`, `responsible_assigned`,
`comment_added`, `approval_required`, `document_registered`, `document_archived`.

## Dashboard

`GET /dashboard/` возвращает данные с учётом object-level access:

```json
{
  "data": {
    "counters": {
      "all": 20,
      "my": 8,
      "for_approval": 3,
      "returned": 2,
      "overdue": 1,
      "archived": 6
    },
    "recent_documents": [],
    "approval_documents": [],
    "recent_notifications": [],
    "quick_actions": []
  },
  "message": "Success"
}
```

## Интеграционные замечания

- UUID передаются строками.
- Все даты — ISO 8601 с timezone; backend работает в `Asia/Bishkek`.
- После мутаций frontend должен использовать статус из ответа, а не вычислять его локально.
- `204 No Content` не содержит envelope/body.
- Не показывайте пользователю действия только по роли: используйте permissions профиля,
  а окончательное решение всегда остаётся за backend object-level проверкой.
>>>>>>> 62d5b43 (docs: add frontend api contract)
