# YandexGPT Chat - Простой веб-интерфейс

Простое Flask приложение для общения с YandexGPT через веб-интерфейс с логированием запросов и ответов.

## Возможности

- 💬 Простой и удобный веб-интерфейс для чата
- 📝 Логирование всех запросов и ответов в файл `chat_logs.log`
- 📚 Сохранение истории диалога в памяти
- 🔄 Контекст последних сообщений для более связного диалога
- 🧹 Возможность очистки истории чата
- 📱 Адаптивный дизайн для мобильных устройств

## Установка и настройка

### 1. Клонирование и установка зависимостей

```bash
# Переходим в папку проекта
cd C:\Users\fedor\PycharmProjects\yandex_llm_chat

# Создаем виртуальное окружение (опционально)
python -m venv venv
venv\Scripts\activate

# Устанавливаем зависимости
pip install -r requirements.txt
```

### 2. Настройка .env файла

Файл `.env` уже создан с базовыми настройками. При необходимости измените:

```env
# Yandex Cloud
SERVICE_ACCOUNT_ID="ajeacsvmpbkbfvldulg0"
KEY_ID="ajeom5pillv2tod6fe9f"
FOLDER_ID="b1gl23cms9rmbng87rm7"
PRIVATE_KEY_PATH=private-key.pem

# YandexGPT настройки
YAND_TEXT_MODEL_URI=gpt://b1gl23cms9rmbng87rm7/yandexgpt/latest
```

### 3. Проверка приватного ключа

Убедитесь, что файл `private-key.pem` находится в корне проекта.

## Запуск

```bash
python app.py
```

Приложение будет доступно по адресу: http://localhost:5000

## Структура проекта

```
yandex_llm_chat/
├── app.py              # Основное Flask приложение
├── yandex_api.py       # API для работы с YandexGPT
├── yandex_auth.py      # Аутентификация с Yandex Cloud
├── settings.py         # Настройки проекта
├── .env               # Переменные окружения
├── private-key.pem    # Приватный ключ сервисного аккаунта
├── requirements.txt   # Зависимости Python
├── chat_logs.log      # Логи чата (создается автоматически)
└── templates/
    └── index.html     # Веб-интерфейс
```

## Использование

1. Откройте http://localhost:5000 в браузере
2. Введите ваш запрос в текстовое поле
3. Нажмите "Отправить" или Enter для отправки
4. Получите ответ от YandexGPT
5. Все запросы и ответы логируются в `chat_logs.log`

## API Endpoints

- `GET /` - Главная страница с интерфейсом
- `POST /api/chat` - Отправка сообщения к YandexGPT
- `GET /api/history` - Получение истории чата
- `GET /api/clear` - Очистка истории чата

## Логирование

Все взаимодействия с моделью логируются в файл `chat_logs.log` со следующей информацией:
- Время запроса
- Текст запроса пользователя
- Ответ YandexGPT
- Ошибки при обработке

## Настройка модели

Для изменения модели YandexGPT отредактируйте параметр `YAND_TEXT_MODEL_URI` в `.env` файле:

```env
# Для YandexGPT Lite
YAND_TEXT_MODEL_URI=gpt://b1gl23cms9rmbng87rm7/yandexgpt-lite/latest

# Для YandexGPT Pro
YAND_TEXT_MODEL_URI=gpt://b1gl23cms9rmbng87rm7/yandexgpt/latest
```

## Безопасность

⚠️ **Важно**: Не размещайте приватный ключ (`private-key.pem`) в публичных репозиториях!

Для продакшена рекомендуется:
- Использовать HTTPS
- Настроить аутентификацию пользователей  
- Хранить логи в безопасном месте
- Использовать базу данных вместо хранения в памяти
