"""Общие фикстуры для всех тестов."""

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import Role, User, UserStatus
from apps.organizations.models import Department

PASSWORD = "TestPass123!"


@pytest.fixture(autouse=True)
def _clear_cache():
    """Кеш (например, системных настроек) не откатывается вместе с БД."""
    cache.clear()
    yield
    cache.clear()


# ---------------------------------------------------------------------------
# Клиенты
# ---------------------------------------------------------------------------


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def auth_client(api):
    """Фабрика: возвращает клиент, авторизованный под переданным пользователем."""

    def _login(user, password=PASSWORD):
        response = api.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": password},
            format="json",
        )
        assert response.status_code == 200, response.json()
        token = response.json()["data"]["access"]
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    return _login


# ---------------------------------------------------------------------------
# Роли
# ---------------------------------------------------------------------------


@pytest.fixture
def roles(db):
    """Роли создаются data-миграцией, просто достаём их."""
    return {role.code: role for role in Role.objects.all()}


# ---------------------------------------------------------------------------
# Подразделения
# ---------------------------------------------------------------------------


@pytest.fixture
def root_department(db):
    return Department.objects.create(name="Ректорат", code="rectorate")


@pytest.fixture
def child_department(db, root_department):
    return Department.objects.create(name="IT отдел", code="it", parent=root_department)


# ---------------------------------------------------------------------------
# Пользователи
# ---------------------------------------------------------------------------


@pytest.fixture
def user_factory(db, roles):
    counter = {"n": 0}

    def _create(
        email=None,
        role_code="employee",
        department=None,
        status=UserStatus.ACTIVE,
        password=PASSWORD,
        **kwargs,
    ):
        counter["n"] += 1
        email = email or f"user{counter['n']}@esu.kg"
        return User.objects.create_user(
            email=email,
            password=password,
            first_name=kwargs.pop("first_name", "Тест"),
            last_name=kwargs.pop("last_name", f"Пользователь{counter['n']}"),
            role=roles.get(role_code),
            department=department,
            status=status,
            **kwargs,
        )

    return _create


@pytest.fixture
def employee(user_factory, child_department):
    return user_factory(email="employee@esu.kg", role_code="employee", department=child_department)


@pytest.fixture
def manager(user_factory, child_department):
    return user_factory(email="manager@esu.kg", role_code="manager", department=child_department)


@pytest.fixture
def admin(user_factory, root_department):
    return user_factory(email="admin@esu.kg", role_code="admin", department=root_department)


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        email="root@esu.kg",
        password=PASSWORD,
        first_name="Супер",
        last_name="Пользователь",
    )


@pytest.fixture
def admin_client(auth_client, admin):
    return auth_client(admin)


@pytest.fixture
def employee_client(auth_client, employee):
    return auth_client(employee)


@pytest.fixture
def manager_client(auth_client, manager):
    return auth_client(manager)
