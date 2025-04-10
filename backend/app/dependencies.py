import firebase_admin
# Убираем импорты firebase_admin.firestore
# from firebase_admin import credentials, firestore
from firebase_admin import credentials
# Возвращаем импорт google.cloud.firestore
from google.cloud import firestore as google_firestore
# Импортируем Credentials для AsyncClient
from google.oauth2 import service_account
# Убираем FirestoreClient
# from google.cloud.firestore_v1.client import Client as FirestoreClient
import logging
from fastapi import HTTPException, Depends
import json
import threading # Для потокобезопасности
# Убрал exceptions, т.к. тестовый запрос убран
import asyncio # Нужен для запуска async функции
from firebase_admin import firestore as admin_firestore # Импортируем firestore из admin
import os
import traceback

logger = logging.getLogger(__name__)

# --- Глобальные переменные ---
_firebase_app = None
_db_client = None
_project_id = None
_init_lock = threading.Lock() # Блокировка для предотвращения гонки инициализации

# Путь к файлу ключа сервисного аккаунта
CRED_PATH = "service-account.json"
DATABASE_ID = '(default)' # Обычно не требуется для AsyncClient с project_id

async def _perform_initialization_async(): # Делаем функцию асинхронной
    """Асинхронная внутренняя функция для выполнения инициализации."""
    logger.info("***** Вход в _perform_initialization_async *****") # <-- Новый лог
    global _firebase_app, _db_client, _project_id

    # Проверяем еще раз под блокировкой, вдруг другой поток уже инициализировал
    if _db_client:
        logger.info("Асинхронная инициализация Firestore уже выполнена другим потоком.")
        return

    logger.info("Попытка асинхронной инициализации Firestore...")
    try:
        # 1. Проверяем существование файла и читаем Project ID из файла ключа (синхронно)
        try:
            if not os.path.exists(CRED_PATH):
                logger.error(f"Файл ключа сервисного аккаунта не найден: {CRED_PATH}")
                logger.error(f"Текущая директория: {os.getcwd()}")
                logger.error(f"Содержимое директории: {os.listdir()}")
                raise FileNotFoundError(f"Файл ключа сервисного аккаунта не найден: {CRED_PATH}")
                
            with open(CRED_PATH, 'r') as f:
                key_data = json.load(f)
                _project_id = key_data.get('project_id')
                logger.info(f"Содержимое ключа: project_id={_project_id}, type={key_data.get('type')}, client_email={key_data.get('client_email')}")
            if not _project_id:
                 raise ValueError(f"project_id не найден в файле ключа: {CRED_PATH}")
            logger.info(f"Прочитан project_id: {_project_id} из {CRED_PATH}")
        except Exception as read_e:
            logger.error(f"Не удалось прочитать project_id из {CRED_PATH}: {read_e}", exc_info=True)
            raise # Перевыбрасываем критическую ошибку

        # 2. Загружаем объект учетных данных GCP (синхронно)
        try:
            gcp_credentials = service_account.Credentials.from_service_account_file(CRED_PATH)
            logger.info(f"Учетные данные GCP загружены: {gcp_credentials}")
            logger.info(f"Scopes: {gcp_credentials.scopes}")
        except Exception as cred_e:
            logger.error(f"Ошибка при загрузке учетных данных GCP: {cred_e}", exc_info=True)
            raise

        # 3. Инициализируем Firebase Admin SDK (синхронно, если еще не инициализирован)
        try:
            if not firebase_admin._apps:
                 logger.info(f"Инициализация Firebase Admin SDK для проекта {_project_id}...")
                 admin_creds = credentials.Certificate(CRED_PATH)
                 _firebase_app = firebase_admin.initialize_app(admin_creds, {
                     'projectId': _project_id,
                 })
                 logger.info(f"Firebase Admin SDK инициализирован: {_firebase_app}")
                 
                 # Протестируем базовую функциональность Firebase SDK
                 try:
                     auth_list = firebase_admin.auth.list_users().users
                     logger.info(f"Успешно получен список пользователей Firebase. Количество: {len(auth_list)}")
                 except Exception as test_e:
                     logger.warning(f"Тест базовой функциональности Firebase SDK не прошел: {test_e}")
            else:
                 logger.info("Используем существующее Firebase приложение по умолчанию.")
                 _firebase_app = firebase_admin.get_app()
        except Exception as firebase_e:
            logger.error(f"Ошибка при инициализации Firebase Admin SDK: {firebase_e}", exc_info=True)
            raise

        # 4. Инициализируем Firestore AsyncClient (асинхронно)
        try:
            logger.info(f"Инициализация google.cloud.firestore.AsyncClient для проекта {_project_id}...")
            
            _db_client = google_firestore.AsyncClient(
                project=_project_id,
                credentials=gcp_credentials
            )
            
            # Тестовый запрос к Firestore для проверки соединения
            try:
                logger.info("Выполняем тестовый запрос к Firestore...")
                collection_ref = _db_client.collection('projects')
                query = collection_ref.limit(1)
                docs = await query.get()
                logger.info(f"Тестовый запрос успешно выполнен. Получено документов: {len(docs)}")
            except Exception as test_e:
                logger.warning(f"Тестовый запрос к Firestore не удался: {test_e}")
                # Продолжаем несмотря на ошибку теста
                
            logger.info("Клиент google.cloud.firestore.AsyncClient УСПЕШНО СОЗДАН.")
        except Exception as firestore_e:
            logger.error(f"Ошибка при инициализации Firestore AsyncClient: {firestore_e}", exc_info=True)
            raise

    except Exception as e:
        logger.error(f"КРИТИЧЕСКАЯ ОШИБКА асинхронной инициализации Firestore клиента: {e}", exc_info=True)
        _db_client = None
        _project_id = None
        # Не выбрасываем HTTPException здесь, чтобы приложение запустилось,
        # но get_db() вернет 503
        # raise HTTPException(status_code=503, detail=f"Ошибка инициализации сервиса базы данных: {e}") from e

async def initialize_firestore_on_startup(): # Делаем функцию async
    """Асинхронная функция для вызова при старте FastAPI для инициализации Firestore."""
    logger.info("***** Вход в initialize_firestore_on_startup *****") # <-- Новый лог
    with _init_lock:
        if _db_client is None or _firebase_app is None: # Проверяем оба
             logger.info("Вызов асинхронной инициализации Firestore и Admin SDK...")
             await _perform_initialization_async()
        else:
             logger.info("Клиенты Firestore и Admin SDK уже были инициализированы ранее.")

# ЗАВИСИМОСТЬ ДЛЯ AsyncClient (google-cloud-firestore)
def get_db() -> google_firestore.AsyncClient:
    """FastAPI зависимость для получения инициализированного Firestore AsyncClient."""
    logger.debug(f"***** Попытка вызова get_db (AsyncClient). Текущий _db_client: {type(_db_client)} *****") # <-- Новый лог
    if _db_client is None:
        logger.critical("КРИТИЧЕСКАЯ ОШИБКА: AsyncClient Firestore не инициализирован!")
        raise HTTPException(status_code=503, detail="Сервис базы данных (AsyncClient) не инициализирован.")
    return _db_client

# НОВАЯ ЗАВИСИМОСТЬ ДЛЯ Admin Firestore Client
def get_admin_db() -> admin_firestore.client:
    logger.debug(f"***** Попытка вызова get_admin_db. Текущий _firebase_app: {type(_firebase_app)} *****")
    if _firebase_app is None:
        logger.critical("КРИТИЧЕСКАЯ ОШИБКА: Firebase Admin SDK не инициализирован!")
        raise HTTPException(status_code=503, detail="Сервис Firebase Admin SDK не инициализирован.")
    # Получаем клиент Firestore из инициализированного Admin App
    # Важно: этот клиент синхронный, но мы будем использовать его в async функциях через sync_to_async или напрямую, если его методы это позволяют.
    # Более правильным было бы использовать Admin SDK > 6.1.0 с его async Firestore, но пока попробуем так.
    try:
        admin_db_client = admin_firestore.client(_firebase_app)
        logger.info(f"Admin Firestore client получен: {type(admin_db_client)}")
        return admin_db_client
    except Exception as e:
        logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА при получении Admin Firestore client: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка получения клиента Admin Firestore: {e}")

# --- Зависимость для получения Firebase Admin App (если нужно где-то еще) ---
def get_firebase_app():
    """FastAPI зависимость для получения инициализированного Firebase Admin app."""
    if _firebase_app is None:
         logger.warning("Firebase Admin app не инициализирован. Попытка инициализации Firestore...")
         # Попытка получить db может затриггерить ошибку, если инициализация не удалась
         try:
             get_db()
         except HTTPException:
              pass # Ошибка уже залоггирована в get_db
         if _firebase_app is None: # Проверяем еще раз
              raise HTTPException(status_code=503, detail="Сервис Firebase Admin недоступен.")
    return _firebase_app