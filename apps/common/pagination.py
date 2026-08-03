"""Пагинация по умолчанию."""

from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """
    Формат ответа:
    {"count": 100, "next": "...", "previous": null, "results": [...]}

    Клиент управляет через query-параметры:
    ?page=2&page_size=50
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class LargePagination(DefaultPagination):
    page_size = 100
    max_page_size = 500
