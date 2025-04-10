import google.generativeai as genai
from googleapiclient.discovery import build
import os
import logging
from dotenv import load_dotenv
from googleapiclient.errors import HttpError
# Убрали зависимости от google.auth, т.к. ключи будем брать из env

# Загружаем переменные окружения здесь тоже
load_dotenv()

logger = logging.getLogger(__name__)

# --- Ключи API (Загрузка из переменных окружения) ---
logger.info("Загрузка ключей API из окружения...")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Логируем, что загрузили (маскируем часть ключа для безопасности)
logger.info(f"GOOGLE_API_KEY: {'Найден' if GOOGLE_API_KEY else 'НЕ НАЙДЕН'}")
if GOOGLE_API_KEY:
    logger.info(f"  (Начало: {GOOGLE_API_KEY[:4]}...)")
logger.info(f"GEMINI_API_KEY: {'Найден' if GEMINI_API_KEY else 'НЕ НАЙДЕН'}")
if GEMINI_API_KEY:
    logger.info(f"  (Начало: {GEMINI_API_KEY[:4]}...)")

# Флаги для отслеживания инициализации
_youtube_api_client = None
_gemini_api_configured = False

# --- Настройка API --- 

def setup_gemini_api():
    """Настраивает Gemini API. Возвращает True в случае успеха, иначе False."""
    global _gemini_api_configured
    logger.info("Попытка настройки Gemini API...")
    if _gemini_api_configured:
        logger.info("Gemini API уже был настроен ранее.")
        return True # Уже настроено
        
    if not GEMINI_API_KEY:
        logger.error("Ключ Gemini API (GEMINI_API_KEY) не найден в переменных окружения!")
        return False
    try:
        logger.info(f"Вызов genai.configure() с ключом (начало: {GEMINI_API_KEY[:4]}...)...")
        genai.configure(api_key=GEMINI_API_KEY)
        _gemini_api_configured = True
        logger.info("Gemini API успешно сконфигурирован (genai.configure выполнен).")
        return True
    except Exception as e:
        logger.error(f"Ошибка конфигурации Gemini API (при вызове genai.configure): {e}", exc_info=True)
        _gemini_api_configured = False
        return False

def get_youtube_api_client():
    """Возвращает инициализированный клиент YouTube API или None при ошибке."""
    global _youtube_api_client
    if _youtube_api_client:
        return _youtube_api_client # Возвращаем существующий клиент
        
    if not GOOGLE_API_KEY:
        logger.error("Ключ YouTube Data API (GOOGLE_API_KEY) не найден в переменных окружения!")
        return None
    try:
        youtube = build('youtube', 'v3', developerKey=GOOGLE_API_KEY)
        # Простая проверка работы клиента
        # request = youtube.channels().list(part='snippet', id='UC_x5XG1OV2P6uZZ5FSM9Ttw') 
        # response = request.execute()
        _youtube_api_client = youtube
        logger.info("Клиент YouTube Data API успешно создан.")
        return youtube
    except HttpError as e:
        logger.error(f"Ошибка HTTP при создании клиента YouTube API: {e}")
        return None
    except Exception as e:
        logger.error(f"Неизвестная ошибка при создании клиента YouTube API: {e}")
        return None

# Меняем модель по умолчанию на gemini-2.0-flash-001 по предложению пользователя
def get_gemini_model(model_name: str = 'models/gemini-2.0-flash-001') -> genai.GenerativeModel | None:
    """Возвращает инстанс модели Gemini, если API настроено."""
    if not _gemini_api_configured:
        logger.warning("Попытка получить модель Gemini до успешной конфигурации API.")
        if not setup_gemini_api(): # Попробуем настроить
             return None
    try:
        model = genai.GenerativeModel(model_name)
        return model
    except Exception as e:
        logger.error(f"Ошибка при создании инстанса модели Gemini '{model_name}': {e}")
        return None

# Вызываем настройку при импорте модуля, чтобы быть готовыми
setup_gemini_api()
get_youtube_api_client()
