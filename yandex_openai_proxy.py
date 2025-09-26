import time
import uuid
import logging
from typing import Any, Dict, List, Union

from flask import Flask, jsonify, request

from yandex_api import yandex_completion, extract_text_from_response

logger = logging.getLogger(__name__)

# Отдельное приложение Flask, чтобы не конфликтовать с основным app.py
proxy_app = Flask(__name__)


def _now_ts() -> int:
    return int(time.time())


def _normalize_messages_for_yandex(messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    norm: List[Dict[str, str]] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        # OpenAI может передавать content списком; приводим к строке
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        norm.append({"role": role, "text": str(content)})
    return norm


@proxy_app.route("/v1/models", methods=["GET"])
def list_models():
    # Возвращаем заглушку списка моделей
    return jsonify({
        "object": "list",
        "data": [
            {"id": "yandex-gpt", "object": "model"}
        ]
    })


@proxy_app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    try:
        data: Dict[str, Any] = request.get_json(force=True) or {}
        messages = data.get("messages", [])
        temperature = float(data.get("temperature", 0.6))
        max_tokens = int(data.get("max_tokens", 2000))

        y_messages = _normalize_messages_for_yandex(messages)

        ya_response = yandex_completion(y_messages, max_tokens=max_tokens, temperature=temperature)
        text = extract_text_from_response(ya_response)

        resp = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
            "object": "chat.completion",
            "created": _now_ts(),
            "model": data.get("model", "yandex-gpt"),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }
        return jsonify(resp)
    except Exception as e:
        logger.exception("/v1/chat/completions failed: %s", e)
        return jsonify({"error": str(e)}), 500


@proxy_app.route("/v1/completions", methods=["POST"])
def completions():
    try:
        data: Dict[str, Any] = request.get_json(force=True) or {}
        prompt: Union[str, List[str]] = data.get("prompt", "")
        temperature = float(data.get("temperature", 0.6))
        max_tokens = int(data.get("max_tokens", 2000))

        if isinstance(prompt, list):
            # Берём первый элемент, если список
            prompt_text = "\n".join(str(p) for p in prompt)
        else:
            prompt_text = str(prompt)

        y_messages = [{"role": "user", "text": prompt_text}]

        ya_response = yandex_completion(y_messages, max_tokens=max_tokens, temperature=temperature)
        text = extract_text_from_response(ya_response)

        resp = {
            "id": f"cmpl-{uuid.uuid4().hex[:24]}",
            "object": "text_completion",
            "created": _now_ts(),
            "model": data.get("model", "yandex-gpt"),
            "choices": [
                {
                    "index": 0,
                    "text": text,
                    "finish_reason": "stop",
                    "logprobs": None,
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }
        return jsonify(resp)
    except Exception as e:
        logger.exception("/v1/completions failed: %s", e)
        return jsonify({"error": str(e)}), 500


def run_proxy(host: str = "127.0.0.1", port: int = 8001):
    # Запуск без дебага и перезагрузчика
    proxy_app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    run_proxy()
