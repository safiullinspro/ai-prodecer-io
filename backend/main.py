import uvicorn
import logging
import logging # Добавляем импорт logging
from fastapi import FastAPI, Request, status, Depends, HTTPException # Добавляем HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from google.cloud import firestore as google_firestore

# Импортируем основной API роутер
from app.api.api import api_router 
# Импортируем остальные роутеры (если они не включены в api_router)
from app.api.endpoints.projects import router as sql_projects_router 
from app.api.endpoints.firebase_projects import router as firebase_projects_router
from app.api.endpoints.firebase_projects_summary import router as firebase_summary_router
from app.youtube_parser.router import router as youtube_parser_router 
# Убираем импорты, связанные с прямым подключением briefing_chat

# Импортируем новую функцию инициализации и зависимости
from app.dependencies import initialize_firestore_on_startup, get_db
from app.services.firebase_auth import get_current_user # Импортируем зависимость пользователя
from app.services import firebase_service # Импортируем сервис
from typing import Dict, Any # Импортируем типы
# Убираем импорт Body, если он больше не нужен напрямую в main.py

# Настройка логирования
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Настройка логирования - Убираем dictConfig, используем getLogger
# dictConfig(LogConfig().dict())
logger = logging.getLogger("uvicorn.error") # Используем стандартный логгер Uvicorn

# Создаем экземпляр FastAPI
app = FastAPI(
    title="AI Producer API",
    description="API для управления проектами и анализа YouTube каналов.",
    version="0.1.0",
)

# Настройка CORS
# ВАЖНО: Для продакшена замени "*" на конкретный домен фронтенда
origins = [
    "http://localhost:3000", # Для локальной разработки Vite
    "http://localhost:5173", # Другой возможный порт Vite
    "http://localhost:3001", # Добавляем порт 3001
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3001", # Добавляем порт 3001
    # "*" # Разрешить все источники (НЕ РЕКОМЕНДУЕТСЯ для продакшена)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], # Явно перечисляем методы
    allow_headers=["*"],
)

# --- Обработчики исключений ---
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.error(f"HTTP Exception: {exc.status_code} {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation Error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled Exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Внутренняя ошибка сервера"},
    )

# --- Подключение роутеров ---

# Подключаем основной API роутер ПЕРВЫМ (содержит auth, parser, chat, briefing)
app.include_router(api_router, prefix="/api") # Добавляем префикс /api

# Используем SQLAlchemy роутеры (временно сохраняем для обратной совместимости)
# app.include_router(sql_projects_router, prefix="/api/projects", tags=["Projects (SQL)"]) # Закомментировано, т.к. используем Firestore

# Добавляем Firebase роутеры (новый подход)
# app.include_router(firebase_projects_router, prefix="/api/v2/projects", tags=["Projects"]) # Старый префикс
app.include_router(firebase_projects_router, prefix="/api/projects", tags=["Projects"]) # Новый префикс для Firestore проектов

# Роутер для сводки (возможно, его нужно будет перенести или интегрировать, пока комментируем)
# app.include_router(firebase_summary_router, prefix="/api/projects", tags=["Projects"]) # Закомментировано, т.к. конфликтует с основным роутером проектов

# Роутер для YouTube Parser (уже использует Firestore)
app.include_router(youtube_parser_router, prefix="/api/youtube", tags=["YouTube Parser"])

# Убираем подключение briefing_chat_router
# app.include_router(briefing_chat_router, prefix="/api", tags=["Briefing Chat"]) 

# Убираем прямое подключение маршрута чата брифинга

# --- Прямое определение эндпоинта удаления ---
@app.delete("/api/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Projects"])
async def delete_project_directly(
    project_id: str,
    db = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Удаление проекта (определено в main.py)"""
    logger.info(f"[main.py] Attempting to delete project {project_id} by user {current_user.get('uid')}")
    # Проверяем, существует ли проект
    project = await firebase_service.get_project_by_id(db, project_id)
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден"
        )
    
    # Проверяем, что проект принадлежит текущему пользователю
    if project.get("owner_id") != current_user["uid"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="У вас нет прав на удаление этого проекта"
        )
    
    # Удаляем проект из Firestore
    success = await firebase_service.delete_project(db, project_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось удалить проект"
        )
    
    # Возвращаем 204 No Content при успехе
    return None
# --- Конец прямого определения эндпоинта ---


# Регистрируем обработчик события startup
@app.on_event("startup")
async def startup_event():
    logger.info("***** Выполняется событие startup в main.py *****")
    try:
        await initialize_firestore_on_startup()
        logger.info("***** Инициализация Firestore в startup_event ЗАВЕРШЕНА УСПЕШНО *****")
    except Exception as e:
        # Логгируем ошибку, но не останавливаем запуск
        logger.critical(f"***** КРИТИЧЕСКАЯ ОШИБКА во время startup_event при вызове initialize_firestore_on_startup: {e} *****", exc_info=True)
        # get_db вернет 503 при запросах

# --- Точка входа для Uvicorn ---
if __name__ == "__main__":
    # Запуск через uvicorn main:app --reload рекомендуется для разработки
    # НО! У нас проблемы с reload, поэтому НЕ используем его при ручном запуске
    uvicorn.run("main:app", host="0.0.0.0", port=8000) # <-- Убран reload=True
