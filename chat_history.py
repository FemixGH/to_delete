import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
import os

logger = logging.getLogger(__name__)

class ChatHistoryManager:
    """Менеджер для работы с историей чата"""

    def __init__(self, history_file: str = 'chat_history.json', log_file: str = 'chat_detailed.log'):
        self.history_file = history_file
        self.log_file = log_file
        self.in_memory_history = []
        self.max_memory_size = 100

        # Настраиваем отдельный логгер для детальной истории
        self.history_logger = logging.getLogger('chat_history')
        self.history_logger.setLevel(logging.INFO)

        # Создаем обработчик для файла с детальной историей
        if not any(isinstance(h, logging.FileHandler) and h.baseFilename.endswith(log_file)
                  for h in self.history_logger.handlers):
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - CHAT - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            self.history_logger.addHandler(file_handler)

        # Загружаем существующую историю при инициализации
        self._load_history()

    def add_chat_entry(self, user_message: str, bot_response: str,
                      user_id: Optional[str] = None, session_id: Optional[str] = None) -> Dict:
        """Добавляет новую запись в историю чата"""
        timestamp = datetime.now().isoformat()

        chat_entry = {
            'id': len(self.in_memory_history) + 1,
            'timestamp': timestamp,
            'user_id': user_id or 'anonymous',
            'session_id': session_id or 'default',
            'user_message': user_message,
            'bot_response': bot_response,
            'message_length': len(user_message),
            'response_length': len(bot_response)
        }

        # Добавляем в память
        self.in_memory_history.append(chat_entry)

        # Ограничиваем размер истории в памяти
        if len(self.in_memory_history) > self.max_memory_size:
            self.in_memory_history.pop(0)

        # Логируем детальную информацию
        self._log_chat_entry(chat_entry)

        # Сохраняем в файл
        self._save_to_file(chat_entry)

        return chat_entry

    def get_recent_history(self, limit: int = 20) -> List[Dict]:
        """Получает последние записи из истории"""
        return self.in_memory_history[-limit:] if limit > 0 else self.in_memory_history

    def get_conversation_context(self, limit: int = 5) -> List[Dict]:
        """Получает контекст для модели (последние сообщения в формате для API)"""
        recent = self.in_memory_history[-limit:]
        messages = []

        for entry in recent:
            messages.append({"role": "user", "text": entry['user_message']})
            messages.append({"role": "assistant", "text": entry['bot_response']})

        return messages

    def clear_history(self) -> None:
        """Очищает историю чата"""
        self.in_memory_history.clear()
        self.history_logger.info("История чата очищена пользователем")

    def get_stats(self) -> Dict:
        """Возвращает статистику по истории чата"""
        if not self.in_memory_history:
            return {'total_messages': 0}

        total_messages = len(self.in_memory_history)
        total_user_chars = sum(entry['message_length'] for entry in self.in_memory_history)
        total_bot_chars = sum(entry['response_length'] for entry in self.in_memory_history)

        return {
            'total_messages': total_messages,
            'total_user_characters': total_user_chars,
            'total_bot_characters': total_bot_chars,
            'average_user_message_length': total_user_chars // total_messages if total_messages > 0 else 0,
            'average_bot_response_length': total_bot_chars // total_messages if total_messages > 0 else 0,
            'first_message_time': self.in_memory_history[0]['timestamp'] if self.in_memory_history else None,
            'last_message_time': self.in_memory_history[-1]['timestamp'] if self.in_memory_history else None
        }

    def search_history(self, query: str, limit: int = 10) -> List[Dict]:
        """Поиск по истории чата"""
        query_lower = query.lower()
        results = []

        for entry in reversed(self.in_memory_history):  # Поиск с конца (более свежие сообщения)
            if (query_lower in entry['user_message'].lower() or
                query_lower in entry['bot_response'].lower()):
                results.append(entry)
                if len(results) >= limit:
                    break

        return results

    def _log_chat_entry(self, entry: Dict) -> None:
        """Логирует запись чата в детальный лог"""
        log_message = (
            f"USER[{entry['user_id']}|{entry['session_id']}]: {entry['user_message']} | "
            f"BOT: {entry['bot_response'][:100]}{'...' if len(entry['bot_response']) > 100 else ''}"
        )
        self.history_logger.info(log_message)

    def _save_to_file(self, entry: Dict) -> None:
        """Сохраняет запись в JSON файл"""
        try:
            # Читаем существующие данные
            existing_data = []
            if os.path.exists(self.history_file):
                try:
                    with open(self.history_file, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                except json.JSONDecodeError:
                    logger.warning(f"Не удалось прочитать {self.history_file}, создается новый файл")

            # Добавляем новую запись
            existing_data.append(entry)

            # Ограничиваем размер файла (оставляем последние 1000 записей)
            if len(existing_data) > 1000:
                existing_data = existing_data[-1000:]

            # Сохраняем обратно
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Ошибка сохранения истории в файл: {e}")

    def _load_history(self) -> None:
        """Загружает историю из файла при инициализации"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                    # Загружаем только последние записи в память
                    self.in_memory_history = file_data[-self.max_memory_size:]
                logger.info(f"Загружена история: {len(self.in_memory_history)} записей")
        except Exception as e:
            logger.error(f"Ошибка загрузки истории из файла: {e}")
            self.in_memory_history = []
