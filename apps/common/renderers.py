"""Единый формат ответа API."""

from rest_framework.renderers import JSONRenderer


class EnvelopeJSONRenderer(JSONRenderer):
    """
    Оборачивает успешные ответы в {"data": ..., "message": "Success"}.
    Ошибки уже приходят в нужном формате из custom_exception_handler,
    поэтому их пропускаем как есть.
    """

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context.get("response")

        # 204 No Content не должен иметь тела
        if response is not None and response.status_code == 204:
            return b""

        # Ответ уже в формате ошибки
        if isinstance(data, dict) and "error" in data:
            return super().render(data, accepted_media_type, renderer_context)

        # Схема OpenAPI и Swagger не оборачиваются
        view = renderer_context.get("view")
        if view is not None and getattr(view, "swagger_fake_view", False):
            return super().render(data, accepted_media_type, renderer_context)

        message = "Success"
        if isinstance(data, dict) and "message" in data and len(data) == 1:
            message = data["message"]
            data = {}

        payload = {"data": data, "message": message}
        return super().render(payload, accepted_media_type, renderer_context)
