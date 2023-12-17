"""Файл с описанием всех кастомных исключений."""


class GlobalTokensError(Exception):
    """Отсутствие одного из токенов."""


class ResponseAPIKeyError(Exception):
    """Отсутствие ожидаемых ключей в ответе API."""


class SendMessageError(Exception):
    """Ошибка при отправке сообщения."""


class EndpointStatusError(Exception):
    """Ошибка, возникающая если статус ответа отличен от 200."""


class RequestExceptionError(Exception):
    """Ошибка, возникающая при недоступности эндпоинта."""


class JSONDecodeError(Exception):
    """Ошибка, возникающая из-за неправильного декодирования JSON."""
