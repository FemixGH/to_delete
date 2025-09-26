import os
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from yandex_api import yandex_completion, extract_text_from_response
import settings

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('chat_logs.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = settings.SECRET_KEY
app.config['DEBUG'] = settings.DEBUG

# Список для хранения истории чата в памяти (в продакшене лучше использовать БД)
chat_history = []


@app.route('/')
def index():
    """Главная страница с интерфейсом чата"""
    return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    """API endpoint для отправки сообщений"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()

        if not user_message:
            return jsonify({'error': 'Сообщение не может быть пустым'}), 400

        # Логируем запрос пользователя
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"[{timestamp}] Запрос пользователя: {user_message}")

        # Получаем контекст из истории (последние 5 сообщений для контекста)
        messages = []

        # Добавляем последние сообщения из истории для контекста
        recent_history = chat_history[-10:]  # последние 10 сообщений
        for item in recent_history:
            messages.append({"role": "user", "text": item['user_message']})
            messages.append({"role": "assistant", "text": item['bot_response']})

        # Добавляем текущее сообщение
        messages.append({"role": "user", "text": user_message})

        # Отправляем запрос к YandexGPT
        response = yandex_completion(messages)
        bot_response = extract_text_from_response(response)

        # Логируем ответ модели
        logger.info(f"[{timestamp}] Ответ YandexGPT: {bot_response}")

        # Сохраняем в историю
        chat_entry = {
            'timestamp': timestamp,
            'user_message': user_message,
            'bot_response': bot_response,
            'raw_response': response  # для отладки
        }
        chat_history.append(chat_entry)

        # Ограничиваем размер истории
        if len(chat_history) > 100:
            chat_history.pop(0)

        return jsonify({
            'response': bot_response,
            'timestamp': timestamp
        })

    except Exception as e:
        error_msg = f"Ошибка сервера: {str(e)}"
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500


@app.route('/api/history')
def get_history():
    """Получение истории чата"""
    # Возвращаем последние 20 сообщений
    recent_history = chat_history[-20:]
    return jsonify(recent_history)


@app.route('/api/clear')
def clear_history():
    """Очистка истории чата"""
    global chat_history
    chat_history = []
    logger.info("История чата очищена")
    return jsonify({'message': 'История очищена'})


if __name__ == '__main__':
    # Создаем папку для шаблонов если её нет
    if not os.path.exists('templates'):
        os.makedirs('templates')

    # Проверяем настройки перед запуском
    if not settings.SERVICE_ACCOUNT_ID or not settings.KEY_ID or not settings.TEXT_MODEL_URI:
        logger.error("Не настроены обязательные параметры в .env файле")
        print("Ошибка: проверьте настройки в .env файле")
    else:
        logger.info("Запуск Flask приложения")
        app.run(host='0.0.0.0', port=5000, debug=settings.DEBUG)
