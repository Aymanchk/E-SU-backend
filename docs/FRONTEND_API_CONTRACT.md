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
  "message": "Success"
}
```

**Ошибка:**

```json
{
  "error": {
    "code": "validation_error",
    "message": "Некорректные данные",
    "details": { "email": ["Обязательное поле."] }
  }
}
```

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
