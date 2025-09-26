import os
import dotenv

# Загружаем переменные окружения из .env
dotenv.load_dotenv()

SERVICE_ACCOUNT_ID = os.getenv("SERVICE_ACCOUNT_ID")
KEY_ID = os.getenv("KEY_ID")
FOLDER_ID = os.getenv("FOLDER_ID")
PRIVATE_KEY_PATH = os.getenv("PRIVATE_KEY_PATH", "private-key.pem")

# URI модели YandexGPT
TEXT_MODEL_URI = os.getenv("YAND_TEXT_MODEL_URI")

# Настройки Flask
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
