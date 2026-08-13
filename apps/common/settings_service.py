"""
Кеширование системных настроек (ТЗ §10).

Настройки читаются часто, а меняются редко, поэтому сериализованный список
кешируется. Кеш инвалидируется после любого изменения через PATCH.
"""

from django.core.cache import cache

from .models import SystemSetting
from .serializers import SystemSettingSerializer

SYSTEM_SETTINGS_CACHE_KEY = "system_settings:all"
SYSTEM_SETTINGS_CACHE_TIMEOUT = 60 * 60  # 1 час


def get_all_settings_data():
    """
    Возвращает список сериализованных настроек (все, без учёта прав).

    Результат кешируется. Фильтрацию публичных/приватных настроек выполняет
    вызывающий код по полю ``is_public``.
    """
    data = cache.get(SYSTEM_SETTINGS_CACHE_KEY)
    if data is None:
        queryset = SystemSetting.objects.all()
        serialized = SystemSettingSerializer(queryset, many=True).data
        # Приводим к обычным dict, чтобы значение безопасно (de)сериализовалось в кеше.
        data = [dict(item) for item in serialized]
        cache.set(SYSTEM_SETTINGS_CACHE_KEY, data, SYSTEM_SETTINGS_CACHE_TIMEOUT)
    return data


def invalidate_settings_cache():
    """Сбрасывает кеш настроек. Вызывается после PATCH /api/v1/settings/."""
    cache.delete(SYSTEM_SETTINGS_CACHE_KEY)
