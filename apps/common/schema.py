"""Обработка OpenAPI схемы под наш формат ответов и версионирование."""


def exclude_legacy_paths(endpoints, **kwargs):
    """
    Preprocessing-хук drf-spectacular.

    Оставляет в схеме только версионированные пути ``/api/v1/…``. Legacy-префикс
    ``/api/…`` подключён ради обратной совместимости, но в Swagger он не нужен и
    создавал бы дубликаты operationId.

    ``endpoints`` — список кортежей ``(path, path_regex, method, callback)``.
    """
    return [e for e in endpoints if e[0].startswith("/api/v1/")]


def envelope_postprocessing_hook(result, generator, request, public):
    """
    Оборачивает схему успешных ответов в {"data": ..., "message": "..."}
    и описывает единый формат ошибок.
    """
    error_schema = {
        "type": "object",
        "properties": {
            "error": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "example": "validation_error"},
                    "message": {"type": "string", "example": "Некорректные данные"},
                    "details": {"type": "object"},
                },
            }
        },
    }

    result.setdefault("components", {}).setdefault("schemas", {})
    result["components"]["schemas"]["ErrorResponse"] = error_schema

    for path in result.get("paths", {}).values():
        for operation in path.values():
            if not isinstance(operation, dict):
                continue
            responses = operation.get("responses", {})

            for code, response in responses.items():
                content = response.get("content", {}).get("application/json")
                if not content or "schema" not in content:
                    continue

                if str(code).startswith(("4", "5")):
                    content["schema"] = {"$ref": "#/components/schemas/ErrorResponse"}
                elif str(code).startswith("2") and str(code) != "204":
                    content["schema"] = {
                        "type": "object",
                        "properties": {
                            "data": content["schema"],
                            "message": {"type": "string", "example": "Success"},
                        },
                    }

    return result
