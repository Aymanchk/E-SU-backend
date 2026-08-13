# Permissions & Roles — E-SU

Права (`permissions`) — атомарные разрешения на действия. Роли — именованные наборы
прав. Frontend **не вычисляет** права по названию роли: готовый список `permissions`
приходит в `GET /api/v1/auth/me/` и в ответе login.

---

## Базовые роли

| code | name | is_system | Назначение |
|---|---|---|---|
| `admin` | Администратор | да | Полный доступ ко всем функциям |
| `manager` | Руководитель | да | Согласование документов, просмотр сотрудников |
| `office` | Канцелярия | да | Регистрация, архивирование, справочники |
| `employee` | Сотрудник | да | Создание и просмотр своих документов |

Системные роли (`is_system=true`) удалять нельзя. Роли и права создаются
data-миграцией (`accounts/migrations/0003_seed_permissions_and_roles.py`).

---

## Права и матрица ролей

| Право (`code`) | Группа | admin | manager | office | employee |
|---|---|:--:|:--:|:--:|:--:|
| `documents.view` | documents | ✅ | ✅ | ✅ | ✅ |
| `documents.create` | documents | ✅ | ✅ | ✅ | ✅ |
| `documents.edit` | documents | ✅ | ✅ | ✅ | — |
| `documents.approve` | documents | ✅ | ✅ | — | — |
| `documents.return` | documents | ✅ | ✅ | — | — |
| `documents.archive` | documents | ✅ | — | ✅ | — |
| `users.manage` | users | ✅ | — | — | — |
| `departments.manage` | departments | ✅ | — | — | — |
| `categories.manage` | categories | ✅ | — | ✅ | — |
| `audit.view` | audit | ✅ | — | — | — |
| `settings.manage` | settings | ✅ | — | — | — |

---

## Список прав для UI (таблица-чекбоксы)

```
GET /api/v1/permissions/          # плоский список, без пагинации
GET /api/v1/permissions/?group=documents
```

Каждый элемент:

```json
{ "id": "uuid", "code": "documents.view", "name": "Просмотр документов",
  "group": "documents", "description": "" }
```

Поле `group` позволяет фронту сгруппировать права по разделам и отрисовать таблицу
чекбоксов «роль × право».

---

## Роли: чтение и изменение

| Method | Endpoint | Назначение | Право |
|---|---|---|---|
| GET | `/api/v1/roles/` | Список ролей (с `permissions` и `users_count`) | авторизован |
| GET | `/api/v1/roles/{id}/` | Роль + `permissions_detail` | авторизован |
| PATCH | `/api/v1/roles/{id}/` | Изменить название/описание роли | `users.manage` |
| PUT | `/api/v1/roles/{id}/permissions/` | Заменить набор прав роли | `users.manage` |

Изменение прав роли (`PUT …/permissions/` с телом `{"permissions": ["documents.view", …]}`):

- существование каждого кода **валидируется**, неизвестные коды не принимаются (`400`);
- старый и новый наборы прав пишутся в аудит (`role permissions change`);
- у последнего администратора нельзя отобрать критические права (защита от privilege
  escalation / самоблокировки);
- в ответе возвращается обновлённый список прав роли.

---

## Как проверяются права на backend

- В `/auth/me/` и login поле `permissions` — плоский список кодов прав пользователя
  (объединение прав его роли).
- ViewSet-ы используют карту `permission_map` (действие → требуемое право) и класс
  `HasPermissionPerAction`. Пример (`UserViewSet`): `create/update/block/activate` →
  `users.manage`, а видимость в `list` дополнительно ограничивается в `get_queryset`.
- Проверка на уровне пользователя — `user.has_permission("<code>")`; у суперпользователя
  и `admin` есть все права.

Соответствие эндпоинтов и прав — см. столбец **Permissions** в
[FRONTEND_API_CONTRACT.md](FRONTEND_API_CONTRACT.md).
