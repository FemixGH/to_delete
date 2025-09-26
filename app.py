import os
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from yandex_api import yandex_completion, extract_text_from_response
from chat_history import ChatHistoryManager
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

# Инициализируем менеджер истории чата
chat_manager = ChatHistoryManager()


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

        # Получаем параметры генерации (с значениями по умолчанию)
        temperature = data.get('temperature', 0.6)
        max_tokens = data.get('max_tokens', 2000)

        # Валидация параметров
        try:
            temperature = float(temperature)
            max_tokens = int(max_tokens)

            # Ограничиваем значения
            temperature = max(0.0, min(1.0, temperature))  # от 0.0 до 1.0
            max_tokens = max(100, min(8000, max_tokens))    # от 100 до 8000
        except (ValueError, TypeError):
            temperature = 0.6
            max_tokens = 2000

        if not user_message:
            return jsonify({'error': 'Сообщение не может быть пустым'}), 400

        # Получаем ID сессии для отслеживания
        session_id = session.get('session_id')
        if not session_id:
            session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            session['session_id'] = session_id

        # Логируем запрос пользователя с параметрами
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"[{timestamp}] Запрос пользователя: {user_message} (temp: {temperature}, tokens: {max_tokens})")

        # Получаем контекст из истории для модели
        messages = chat_manager.get_conversation_context(limit=5)

        # Добавляем текущее сообщение
        messages.append({"role": "user", "text": user_message})

        # Отправляем запрос к YandexGPT с настройками
        response = yandex_completion(messages, max_tokens=max_tokens, temperature=temperature)
        bot_response = extract_text_from_response(response)

        # Логируем ответ модели
        logger.info(f"[{timestamp}] Ответ YandexGPT: {bot_response}")

        # Сохраняем в историю через менеджер
        chat_entry = chat_manager.add_chat_entry(
            user_message=user_message,
            bot_response=bot_response,
            user_id=request.remote_addr,  # IP как идентификатор пользователя
            session_id=session_id
        )

        return jsonify({
            'response': bot_response,
            'timestamp': timestamp,
            'message_id': chat_entry['id'],
            'settings': {
                'temperature': temperature,
                'max_tokens': max_tokens
            }
        })

    except Exception as e:
        error_msg = f"Ошибка сервера: {str(e)}"
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500


@app.route('/api/history')
def get_history():
    """Получение истории чата"""
    limit = request.args.get('limit', 20, type=int)
    history = chat_manager.get_recent_history(limit)
    return jsonify(history)


@app.route('/api/chats', methods=['GET'])
def get_chats():
    """Получение списка всех чатов"""
    try:
        chats = chat_manager.get_chat_list()
        return jsonify({
            'chats': chats,
            'current_chat_id': chat_manager.get_current_chat_id()
        })
    except Exception as e:
        logger.error(f"Ошибка получения списка чатов: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/chats', methods=['POST'])
def create_chat():
    """Создание нового чата"""
    try:
        data = request.get_json() or {}
        title = data.get('title', None)

        chat_id = chat_manager.create_new_chat(title)
        chat_manager.load_chat(chat_id)  # Делаем новый чат активным

        return jsonify({
            'chat_id': chat_id,
            'message': 'Новый чат создан'
        })
    except Exception as e:
        logger.error(f"Ошибка создания чата: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/chats/<chat_id>', methods=['GET'])
def load_chat(chat_id):
    """Загрузка конкретного чата"""
    try:
        success = chat_manager.load_chat(chat_id)
        if success:
            history = chat_manager.get_recent_history(100)  # Загружаем больше истории
            return jsonify({
                'chat_id': chat_id,
                'history': history,
                'message': 'Чат загружен'
            })
        else:
            return jsonify({'error': 'Чат не найден'}), 404
    except Exception as e:
        logger.error(f"Ошибка загрузки чата {chat_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/chats/<chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    """Удаление чата"""
    try:
        success = chat_manager.delete_chat(chat_id)
        if success:
            return jsonify({'message': 'Чат удален'})
        else:
            return jsonify({'error': 'Чат не найден'}), 404
    except Exception as e:
        logger.error(f"Ошибка удаления чата {chat_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/chats/<chat_id>/rename', methods=['POST'])
def rename_chat(chat_id):
    """Переименование чата"""
    try:
        data = request.get_json()
        new_title = data.get('title', '').strip()

        if not new_title:
            return jsonify({'error': 'Название не может быть пустым'}), 400

        success = chat_manager.rename_chat(chat_id, new_title)
        if success:
            return jsonify({'message': 'Чат переименован'})
        else:
            return jsonify({'error': 'Чат не найден'}), 404
    except Exception as e:
        logger.error(f"Ошибка переименования чата {chat_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/clear')
def clear_history():
    """Очистка текущего чата"""
    chat_manager.clear_current_chat()
    logger.info("Текущий чат очищен")
    return jsonify({'message': 'Чат очищен'})

@app.route('/api/stats')
def get_chat_stats():
    """Получение статистики по чату"""
    stats = chat_manager.get_stats()
    return jsonify(stats)


@app.route('/api/search')
def search_history():
    """Поиск по истории чата"""
    query = request.args.get('q', '').strip()
    limit = request.args.get('limit', 10, type=int)

    if not query:
        return jsonify({'error': 'Запрос для поиска не может быть пустым'}), 400

    results = chat_manager.search_history(query, limit)
    return jsonify({
        'query': query,
        'results': results,
        'count': len(results)
    })

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
