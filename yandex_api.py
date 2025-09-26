import logging
import requests
from typing import Dict, Any, List, Union
from yandex_auth import get_headers, BASE_URL
from settings import TEXT_MODEL_URI

logger = logging.getLogger(__name__)


def yandex_completion(prompt: Union[str, List[Dict]], max_tokens: int = 2000, temperature: float = 0.6) -> Dict[str, Any]:
    """
    Получение ответа от YandexGPT

    Args:
        prompt: Строка с запросом или список сообщений в формате [{"role": "user", "text": "..."}]
        max_tokens: Максимальное количество токенов в ответе
        temperature: Температура генерации (0.0 - детерминированно, 1.0 - креативно)

    Returns:
        Словарь с ответом API или ошибкой
    """
    url = f"{BASE_URL}/completion"

    # Форматируем промпт в правильный формат для API
    if isinstance(prompt, str):
        messages = [{"role": "user", "text": prompt}]
    elif isinstance(prompt, list):
        messages = []
        for msg in prompt:
            if isinstance(msg, dict) and "role" in msg and "text" in msg:
                messages.append({
                    "role": msg["role"],
                    "text": msg["text"]
                })
            else:
                logger.warning(f"Неправильный формат сообщения: {msg}")
        if not messages:
            messages = [{"role": "user", "text": str(prompt)}]
    else:
        messages = [{"role": "user", "text": str(prompt)}]

    payload = {
        "modelUri": TEXT_MODEL_URI,
        "completionOptions": {
            "stream": False,
            "temperature": temperature,
            "maxTokens": max_tokens
        },
        "messages": messages
    }

    try:
        headers = get_headers()
        logger.info(f"Отправка запроса к YandexGPT: {len(str(messages))} символов")

        response = requests.post(url, headers=headers, json=payload, timeout=60)

        if response.status_code == 200:
            result = response.json()
            logger.info("Успешный ответ от YandexGPT")
            return result
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.error(f"Ошибка API YandexGPT: {error_msg}")
            return {"error": error_msg}

    except requests.exceptions.Timeout:
        error_msg = "Таймаут запроса к YandexGPT"
        logger.error(error_msg)
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"Ошибка при запросе к YandexGPT: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}


def extract_text_from_response(response: Dict[str, Any]) -> str:
    """
    Извлекает текст ответа из ответа API
    """
    if "error" in response:
        return f"Ошибка: {response['error']}"

    try:
        # Структура ответа YandexGPT: result.alternatives[0].message.text
        alternatives = response.get("result", {}).get("alternatives", [])
        if alternatives:
            message = alternatives[0].get("message", {})
            return message.get("text", "Пустой ответ")
        else:
            return "Не удалось получить ответ"
    except (KeyError, IndexError, TypeError) as e:
        logger.error(f"Ошибка парсинга ответа: {e}")
        return f"Ошибка парсинга ответа: {str(e)}"
