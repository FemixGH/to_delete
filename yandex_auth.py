import os
import time
import jwt
import requests
import logging
from datetime import datetime
from settings import SERVICE_ACCOUNT_ID, KEY_ID, PRIVATE_KEY_PATH

logger = logging.getLogger(__name__)

# Базовый URL для API Yandex Cloud
BASE_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1"

# Кэш для IAM токена
_iam_token = None
_token_expires_at = 0


def load_private_key_from_pem(pem_file_path: str) -> str:
    """Загружает приватный ключ из PEM файла"""
    try:
        with open(pem_file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"PEM файл не найден: {pem_file_path}")
        raise
    except Exception as e:
        logger.error(f"Ошибка при чтении PEM файла: {e}")
        raise


def create_jwt(sa_id, key_id, private_key):
    """Создает JWT токен для аутентификации"""
    now = int(time.time())
    payload = {
        "aud": "https://iam.api.cloud.yandex.net/iam/v1/tokens",
        "iss": sa_id,
        "iat": now,
        "exp": now + 360  # 6 минут жизни JWT
    }
    encoded = jwt.encode(
        payload,
        private_key,
        algorithm="PS256",
        headers={"kid": key_id}
    )
    return encoded


def exchange_jwt_for_iam_token(jwt_token):
    """Обменивает JWT на IAM токен"""
    resp = requests.post(
        "https://iam.api.cloud.yandex.net/iam/v1/tokens",
        json={"jwt": jwt_token},
        timeout=10
    )
    if resp.status_code != 200:
        logger.error(f"Ошибка получения IAM токена: {resp.status_code} {resp.text}")
        raise Exception(f"IAM token error: {resp.status_code}")

    data = resp.json()
    return data["iamToken"], data["expiresAt"]


def parse_expires_at(expires_at_str):
    """Парсит строку времени с поддержкой микросекунд"""
    try:
        # Убираем микросекунды, если они есть
        if '.' in expires_at_str:
            # Разделяем на основную часть и микросекунды
            main_part, microsecond_part = expires_at_str.split('.')
            # Берем только основную часть времени
            expires_at_str = main_part + 'Z'

        # Парсим время без микросекунд
        dt = datetime.strptime(expires_at_str, "%Y-%m-%dT%H:%M:%SZ")
        return dt.timestamp()
    except Exception as e:
        logger.error(f"Ошибка парсинга времени {expires_at_str}: {e}")
        # Возвращаем время через час в случае ошибки
        return time.time() + 3600


def get_iam_token():
    """Получает или обновляет IAM токен"""
    global _iam_token, _token_expires_at

    # Проверяем, нужно ли обновить токен
    if _iam_token and time.time() < _token_expires_at - 60:  # обновляем за минуту до истечения
        return _iam_token

    try:
        # Загружаем приватный ключ
        private_key = load_private_key_from_pem(PRIVATE_KEY_PATH)

        # Создаем JWT
        jwt_token = create_jwt(SERVICE_ACCOUNT_ID, KEY_ID, private_key)

        # Обмениваем JWT на IAM токен
        iam_token, expires_at = exchange_jwt_for_iam_token(jwt_token)

        # Кэшируем токен
        _iam_token = iam_token
        _token_expires_at = parse_expires_at(expires_at)

        logger.info("IAM токен успешно получен")
        return iam_token

    except Exception as e:
        logger.error(f"Ошибка получения IAM токена: {e}")
        raise


def get_headers():
    """Возвращает заголовки для запросов к API"""
    iam_token = get_iam_token()
    return {
        "Authorization": f"Bearer {iam_token}",
        "Content-Type": "application/json"
    }
