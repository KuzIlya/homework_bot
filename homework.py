import json
import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (EndpointStatusError, GlobalTokensError,
                        JSONDecodeError, RequestExceptionError,
                        ResponseAPIKeyError, SendMessageError)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

logging.basicConfig(
    format='%(asctime)s, %(levelname)s, %(message)s',
    level=logging.DEBUG,
    filemode='w',
    filename='main.log'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

MISSING_TOKEN_ERROR = 'Отсутствует обязательная переменная окружения: {token}'
EMPTY_TOKEN_ERROR = 'Пустая обязательная переменная окружения: {token}'
SEND_MESSAGE_ERROR = '{error}, {message}'
ENDPOINT_STATUS_ERROR = '{status}, {url}, {headers}, {params}'
JSON_DECODE_ERROR = 'Ошибка при декодировании json, {error}'
REQUEST_EXCEPTION_ERROR = 'Ошибка при доступе к API {error}'
EMPTY_LIST_ERROR = 'Список пуст'
RESPONSE_NOT_DICT = 'response не является словарем'
HOMEWORKS_VALUE_NOT_LIST = 'По ключу homeworks данные не являются списком'
RESPONSE_KEY_ERROR = 'Отсутствие ожидаемых ключей в response'
UNDEFINED_DICT_KEY_ERROR = 'Ключ в словаре не найден, {error}'


def check_tokens() -> bool:
    """Проверяет доступность переменных окружения."""
    for token in (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID):
        if token is None:
            logger.critical(EMPTY_TOKEN_ERROR.format(token=token))
            return False
        if not token:
            logger.critical(MISSING_TOKEN_ERROR.format(token=token))
            return False
    return True


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправляет сообщение в чат, определяемый TELEGRAM_CHAT_ID."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        msg = SEND_MESSAGE_ERROR.format(error=error, message=message)
        logger.error(msg)
        raise SendMessageError(msg) from error
    logging.debug(f'Сообщение отправлено: {message}')


def get_api_answer(timestamp: int) -> dict:
    """Делает запрос к эндпоинту API-сервиса."""
    params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }
    try:
        response = requests.get(**params)
        if response.status_code != HTTPStatus.OK:
            msg = ENDPOINT_STATUS_ERROR.format(
                status=response.status_code,
                **params
            )
            logger.error(msg)
            raise EndpointStatusError(msg)
        return response.json()
    except requests.exceptions.RequestException as error:
        msg = REQUEST_EXCEPTION_ERROR.format(error=error)
        logger.error(msg)
        raise RequestExceptionError(msg) from error
    except json.JSONDecodeError as error:
        msg = JSON_DECODE_ERROR.format(error=error)
        logger.error(msg)
        raise JSONDecodeError(msg) from error


def check_response(response: dict) -> dict:
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        logger.error(RESPONSE_NOT_DICT)
        raise TypeError(RESPONSE_NOT_DICT)
    if response.get('homeworks') is None:
        logger.error(RESPONSE_KEY_ERROR)
        raise ResponseAPIKeyError(RESPONSE_KEY_ERROR)
    if not isinstance(response['homeworks'], list):
        logger.error(HOMEWORKS_VALUE_NOT_LIST)
        raise TypeError(HOMEWORKS_VALUE_NOT_LIST)
    try:
        return response.get('homeworks')[0]
    except IndexError as error:
        logger.error(EMPTY_LIST_ERROR)
        raise IndexError(EMPTY_LIST_ERROR) from error


def parse_status(homework: dict) -> str:
    """Извлекает из информации о конкретной домашней работе статус."""
    try:
        homework_name = homework['homework_name']
        status = homework['status']
        verdict = HOMEWORK_VERDICTS[status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    except KeyError as error:
        logger.error(UNDEFINED_DICT_KEY_ERROR.format(error=error))
        raise KeyError(UNDEFINED_DICT_KEY_ERROR.format(error=error)) from error


def main() -> None:
    """Основная логика работы бота."""
    if not check_tokens():
        raise GlobalTokensError('Отсутствие глобальной переменной')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            send_message(bot, message)
            timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
