import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
import os
import uuid

logger = logging.getLogger(__name__)

class ChatHistoryManager:
    """Менеджер для работы с множественными чатами"""
    
    def __init__(self, chats_dir: str = 'chats', log_file: str = 'chat_detailed.log'):
        self.chats_dir = chats_dir
        self.log_file = log_file
        self.current_chat_id = None
        self.current_chat_history = []
        self.max_memory_size = 100
        
        # Создаем папку для чатов если её нет
        if not os.path.exists(self.chats_dir):
            os.makedirs(self.chats_dir)
        
        # Настраиваем отдельный логгер для детальной истории
        self.history_logger = logging.getLogger('chat_history')
        self.history_logger.setLevel(logging.INFO)
        
        # Создаем обработчик для файла с детальной историей
        if not any(isinstance(h, logging.FileHandler) and h.baseFilename.endswith(log_file) 
                  for h in self.history_logger.handlers):
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - CHAT[%(chat_id)s] - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            self.history_logger.addHandler(file_handler)
    
    def create_new_chat(self, title: str = None) -> str:
        """Создает новый чат и возвращает его ID"""
        chat_id = str(uuid.uuid4())[:8]  # Короткий уникальный ID
        
        if not title:
            title = f"Чат {datetime.now().strftime('%d.%m %H:%M')}"
        
        chat_data = {
            'id': chat_id,
            'title': title,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'messages': []
        }
        
        self._save_chat_to_file(chat_id, chat_data)
        logger.info(f"Создан новый чат: {chat_id} - {title}")
        
        return chat_id
    
    def load_chat(self, chat_id: str) -> bool:
        """Загружает указанный чат"""
        try:
            chat_data = self._load_chat_from_file(chat_id)
            if chat_data:
                self.current_chat_id = chat_id
                self.current_chat_history = chat_data.get('messages', [])
                logger.info(f"Загружен чат: {chat_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка загрузки чата {chat_id}: {e}")
            return False
    
    def get_chat_list(self) -> List[Dict]:
        """Возвращает список всех чатов"""
        chats = []
        try:
            for filename in os.listdir(self.chats_dir):
                if filename.endswith('.json'):
                    chat_id = filename[:-5]  # убираем .json
                    try:
                        chat_data = self._load_chat_from_file(chat_id)
                        if chat_data:
                            # Получаем краткую информацию о чате
                            messages_count = len(chat_data.get('messages', []))
                            last_message = None
                            if messages_count > 0:
                                last_msg = chat_data['messages'][-1]
                                last_message = last_msg.get('user_message', '')[:50]
                                if len(last_message) > 47:
                                    last_message += '...'
                            
                            chat_info = {
                                'id': chat_id,
                                'title': chat_data.get('title', f'Чат {chat_id}'),
                                'created_at': chat_data.get('created_at'),
                                'updated_at': chat_data.get('updated_at'),
                                'messages_count': messages_count,
                                'last_message': last_message
                            }
                            chats.append(chat_info)
                    except Exception as e:
                        logger.error(f"Ошибка чтения чата {chat_id}: {e}")
                        continue
            
            # Сортируем по дате обновления (новые сверху)
            chats.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
            
        except Exception as e:
            logger.error(f"Ошибка получения списка чатов: {e}")
        
        return chats
    
    def delete_chat(self, chat_id: str) -> bool:
        """Удаляет чат"""
        try:
            file_path = os.path.join(self.chats_dir, f"{chat_id}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Чат {chat_id} удален")
                
                # Если это был текущий чат, очищаем состояние
                if self.current_chat_id == chat_id:
                    self.current_chat_id = None
                    self.current_chat_history = []
                
                return True
        except Exception as e:
            logger.error(f"Ошибка удаления чата {chat_id}: {e}")
        
        return False
    
    def rename_chat(self, chat_id: str, new_title: str) -> bool:
        """Переименовывает чат"""
        try:
            chat_data = self._load_chat_from_file(chat_id)
            if chat_data:
                chat_data['title'] = new_title
                chat_data['updated_at'] = datetime.now().isoformat()
                self._save_chat_to_file(chat_id, chat_data)
                logger.info(f"Чат {chat_id} переименован в: {new_title}")
                return True
        except Exception as e:
            logger.error(f"Ошибка переименования чата {chat_id}: {e}")
        
        return False
    
    def add_chat_entry(self, user_message: str, bot_response: str, 
                      user_id: Optional[str] = None, session_id: Optional[str] = None) -> Dict:
        """Добавляет новую запись в текущий чат"""
        if not self.current_chat_id:
            # Создаем новый чат если нет активного
            self.current_chat_id = self.create_new_chat()
            self.current_chat_history = []
        
        timestamp = datetime.now().isoformat()
        
        chat_entry = {
            'id': len(self.current_chat_history) + 1,
            'timestamp': timestamp,
            'user_id': user_id or 'anonymous',
            'session_id': session_id or 'default',
            'user_message': user_message,
            'bot_response': bot_response,
            'message_length': len(user_message),
            'response_length': len(bot_response)
        }
        
        # Добавляем в текущую историю
        self.current_chat_history.append(chat_entry)
        
        # Ограничиваем размер истории в памяти
        if len(self.current_chat_history) > self.max_memory_size:
            self.current_chat_history.pop(0)
        
        # Логируем детальную информацию
        self._log_chat_entry(chat_entry)
        
        # Сохраняем в файл
        self._save_current_chat()
        
        return chat_entry
    
    def get_recent_history(self, limit: int = 20) -> List[Dict]:
        """Получает последние записи из текущего чата"""
        if not self.current_chat_history:
            return []
        return self.current_chat_history[-limit:] if limit > 0 else self.current_chat_history
    
    def get_conversation_context(self, limit: int = 5) -> List[Dict]:
        """Получает контекст для модели (последние сообщения в формате для API)"""
        recent = self.current_chat_history[-limit:]
        messages = []
        
        for entry in recent:
            messages.append({"role": "user", "text": entry['user_message']})
            messages.append({"role": "assistant", "text": entry['bot_response']})
        
        return messages
    
    def clear_current_chat(self) -> None:
        """Очищает текущий чат"""
        if self.current_chat_id:
            self.current_chat_history.clear()
            self._save_current_chat()
            self.history_logger.info("Текущий чат очищен", extra={'chat_id': self.current_chat_id})
    
    def get_current_chat_id(self) -> Optional[str]:
        """Возвращает ID текущего чата"""
        return self.current_chat_id
    
    def _save_current_chat(self):
        """Сохраняет текущий чат в файл"""
        if not self.current_chat_id:
            return
        
        try:
            # Загружаем полные данные чата
            chat_data = self._load_chat_from_file(self.current_chat_id)
            if not chat_data:
                chat_data = {
                    'id': self.current_chat_id,
                    'title': f"Чат {datetime.now().strftime('%d.%m %H:%M')}",
                    'created_at': datetime.now().isoformat(),
                    'messages': []
                }
            
            # Обновляем сообщения и время обновления
            chat_data['messages'] = self.current_chat_history
            chat_data['updated_at'] = datetime.now().isoformat()
            
            self._save_chat_to_file(self.current_chat_id, chat_data)
            
        except Exception as e:
            logger.error(f"Ошибка сохранения текущего чата: {e}")
    
    def _load_chat_from_file(self, chat_id: str) -> Optional[Dict]:
        """Загружает чат из файла"""
        file_path = os.path.join(self.chats_dir, f"{chat_id}.json")
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки чата из файла {file_path}: {e}")
        return None
    
    def _save_chat_to_file(self, chat_id: str, chat_data: Dict):
        """Сохраняет чат в файл"""
        file_path = os.path.join(self.chats_dir, f"{chat_id}.json")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(chat_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения чата в файл {file_path}: {e}")
    
    def _log_chat_entry(self, entry: Dict) -> None:
        """Логирует запись чата в детальный лог"""
        log_message = (
            f"USER[{entry['user_id']}|{entry['session_id']}]: {entry['user_message']} | "
            f"BOT: {entry['bot_response'][:100]}{'...' if len(entry['bot_response']) > 100 else ''}"
        )
        self.history_logger.info(log_message, extra={'chat_id': self.current_chat_id or 'unknown'})

    def get_stats(self) -> Dict:
        """Возвращает статистику по текущему чату"""
        if not self.current_chat_history:
            return {'total_messages': 0}

        total_messages = len(self.current_chat_history)
        total_user_chars = sum(entry['message_length'] for entry in self.current_chat_history)
        total_bot_chars = sum(entry['response_length'] for entry in self.current_chat_history)

        return {
            'total_messages': total_messages,
            'total_user_characters': total_user_chars,
            'total_bot_characters': total_bot_chars,
            'average_user_message_length': total_user_chars // total_messages if total_messages > 0 else 0,
            'average_bot_response_length': total_bot_chars // total_messages if total_messages > 0 else 0,
            'first_message_time': self.current_chat_history[0]['timestamp'] if self.current_chat_history else None,
            'last_message_time': self.current_chat_history[-1]['timestamp'] if self.current_chat_history else None,
            'current_chat_id': self.current_chat_id
        }

    def search_history(self, query: str, limit: int = 10) -> List[Dict]:
        """Поиск по истории текущего чата"""
        query_lower = query.lower()
        results = []

        for entry in reversed(self.current_chat_history):  # Поиск с конца (более свежие сообщения)
            if (query_lower in entry['user_message'].lower() or
                query_lower in entry['bot_response'].lower()):
                results.append(entry)
                if len(results) >= limit:
                    break

        return results

    # Методы для обратной совместимости со старым API
    def clear_history(self) -> None:
        """Алиас для clear_current_chat()"""
        self.clear_current_chat()
