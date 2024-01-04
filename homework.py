import json
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (EndpointStatusError, GlobalTokensError,
                        JSONDecodeError, RequestExceptionError,
                        ResponseAPIKeyError)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(
    logging.StreamHandler(sys.stdout)
)

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
RESPONSE_KEY_ERROR_WITH_INFO = 'Отсутствие ожидаемых ключей в response {error}'
UNDEFINED_DICT_KEY_ERROR = 'Ключ в словаре не найден, {error}'

LOG_SEND_REQUEST = ('Программа начала запрос по url: {url}, '
                    'headers: {headers}, params: {params}')


def check_tokens() -> list:
    """Проверяет доступность переменных окружения."""
    tokens_info = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }

    missing_tokens = [
        token_name
        for token_name, token_value in tokens_info.items()
        if token_value is None
    ]

    if missing_tokens:
        for token_name in missing_tokens:
            logger.critical('Пустая обязательная переменная окружения: '
                            f'{token_name} со значением: None')
    return missing_tokens


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправляет сообщение в чат, определяемый TELEGRAM_CHAT_ID."""
    try:
        logger.debug('Начало отправки сообщения')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        msg = SEND_MESSAGE_ERROR.format(error=error, message=message)
        logger.error(msg)
    else:
        logging.debug(f'Сообщение отправлено: {message}')


def get_api_answer(timestamp: int) -> dict:
    """Делает запрос к эндпоинту API-сервиса."""
    params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }
    try:
        logger.debug(LOG_SEND_REQUEST.format(**params))
        response = requests.get(**params)
        if response.status_code != HTTPStatus.OK:
            msg = ENDPOINT_STATUS_ERROR.format(
                status=response.status_code,
                **params
            )
            raise EndpointStatusError(msg)
        return response.json()
    except requests.exceptions.RequestException as error:
        msg = REQUEST_EXCEPTION_ERROR.format(error=error)
        raise RequestExceptionError(msg) from error
    except json.JSONDecodeError as error:
        msg = JSON_DECODE_ERROR.format(error=error)
        raise JSONDecodeError(msg) from error


def check_response(response: dict) -> dict:
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(RESPONSE_NOT_DICT)

    homeworks = response.get('homeworks')

    if homeworks is None:
        raise ResponseAPIKeyError(RESPONSE_KEY_ERROR)
    if not isinstance(homeworks, list):
        raise TypeError(HOMEWORKS_VALUE_NOT_LIST)

    return homeworks


def parse_status(homework: dict) -> str:
    """Извлекает из информации о конкретной домашней работе статус."""
    try:
        homework_name = homework['homework_name']
        status = homework['status']
        verdict = HOMEWORK_VERDICTS[status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    except KeyError as error:
        raise KeyError(UNDEFINED_DICT_KEY_ERROR.format(error=error)) from error


def main() -> None:
    """Основная логика работы бота."""
    if token_names := check_tokens():
        raise GlobalTokensError(
            ', '.join(
                f'{token_name}: None'
                for token_name in token_names
            )
        )

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 0
    old_status = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)[0]
            message = parse_status(homework)

            if old_status != message:
                send_message(bot, message)
                old_status = message

            timestamp = response.get('current_date', timestamp)
        except ResponseAPIKeyError as error:
            logger.error(RESPONSE_KEY_ERROR_WITH_INFO.format(error=error))
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if old_status != message:
                old_status = message
                send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format=('%(asctime)s, %(module)s, %(lineno)s, '
                '%(funcName)s, %(levelname)s, %(message)s'),
        level=logging.DEBUG,
        filemode='w',
        filename='main.log'
    )
    main()
