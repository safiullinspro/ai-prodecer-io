from fastapi import APIRouter

api_router = APIRouter()

# Импорт и подключение роутеров для различных эндпоинтов
from app.api.endpoints import parser, auth, chat, website_import # Добавили website_import

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(parser.router, prefix="/parser", tags=["parser"])
# Убираем подключение projects.router отсюда
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
# Добавляем новый роутер для импорта с сайта
api_router.include_router(website_import.router, tags=["Website Import"]) # Префикс задан внутри роутера (/website-import)
