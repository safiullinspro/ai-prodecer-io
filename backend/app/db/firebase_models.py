"""
Модели данных для Firestore.
Структура коллекций и документов для хранения данных в Firebase Firestore.
"""
from typing import Dict, List, Optional, Any, TypedDict
from datetime import datetime
from pydantic import BaseModel, Field

# TypedDict для представления структуры документов в Firestore

class FirebaseChatMessage(TypedDict):
    """Сообщение чата в Firestore"""
    id: str  # Уникальный ID сообщения
    project_id: str  # ID проекта
    role: str  # 'user' или 'assistant'
    content: str  # Содержимое сообщения
    created_at: datetime  # Время создания


class FirebaseBriefingData(TypedDict, total=False):
    """Данные брифинга в Firestore"""
    utp: Optional[str]  # Уникальное торговое предложение
    product_description: Optional[str]  # Описание продукта
    funnel_elements: Optional[List[Dict[str, Any]]]  # Элементы воронки
    completion_percentage: int  # Процент заполнения (0-100)
    stage_summary: Optional[str]  # Краткое описание этапа


class FirebaseProject(TypedDict):
    """Проект в Firestore"""
    id: str  # Уникальный ID проекта
    name: str  # Название проекта
    description: Optional[str]  # Описание проекта
    owner_id: str  # ID владельца (user.uid)
    status: str  # Статус проекта (например, "briefing")
    briefing_data: Optional[FirebaseBriefingData]  # Данные брифинга
    created_at: datetime  # Время создания
    updated_at: Optional[datetime]  # Время обновления


class FirebaseUser(TypedDict, total=False):
    """Пользователь в Firestore"""
    uid: str  # Уникальный ID пользователя (из Firebase Auth)
    email: str  # Email пользователя
    username: Optional[str]  # Имя пользователя
    is_active: bool  # Активен ли пользователь
    created_at: datetime  # Время создания
    updated_at: Optional[datetime]  # Время обновления
    photoURL: Optional[str]  # URL фото профиля
    provider: Optional[str]  # Провайдер аутентификации (google, email)


# Pydantic модели для валидации данных при работе с API

class ChatMessageCreate(BaseModel):
    """Модель для создания сообщения чата"""
    content: str

    class Config:
        schema_extra = {
            "example": {
                "content": "Привет! Расскажи о своем продукте."
            }
        }


class ChatMessageResponse(BaseModel):
    """Модель для ответа с сообщением чата"""
    id: str
    project_id: str
    role: str
    content: str
    created_at: datetime

    class Config:
        schema_extra = {
            "example": {
                "id": "abc123",
                "project_id": "project123",
                "role": "assistant",
                "content": "Привет! Я готов помочь с вашим проектом.",
                "created_at": "2023-01-01T12:00:00Z"
            }
        }


class ProjectCreate(BaseModel):
    """Модель для создания проекта"""
    name: str
    description: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "name": "Мой новый проект",
                "description": "Описание моего проекта"
            }
        }


class ProjectUpdate(BaseModel):
    """Модель для обновления проекта"""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    briefing_data: Optional[Dict[str, Any]] = None

    class Config:
        schema_extra = {
            "example": {
                "name": "Обновленное название проекта",
                "status": "analysis"
            }
        }


class ProjectResponse(BaseModel):
    """Модель для ответа с проектом"""
    id: str
    name: str
    description: Optional[str] = None
    owner_id: str
    status: str
    briefing_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        schema_extra = {
            "example": {
                "id": "project123",
                "name": "Мой проект",
                "description": "Описание проекта",
                "owner_id": "user123",
                "status": "briefing",
                "briefing_data": {
                    "utp": "Уникальное предложение",
                    "completion_percentage": 75
                },
                "created_at": "2023-01-01T12:00:00Z",
                "updated_at": "2023-01-02T15:30:00Z"
            }
        }


class UserResponse(BaseModel):
    """Модель для ответа с пользователем"""
    uid: str
    email: str
    username: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None
    photoURL: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "uid": "user123",
                "email": "user@example.com",
                "username": "username",
                "is_active": True,
                "created_at": "2023-01-01T12:00:00Z",
                "photoURL": "https://example.com/photo.jpg"
            }
        }


# Вспомогательные функции для работы с моделями Firestore

def format_firestore_timestamp(timestamp) -> datetime:
    """Преобразует Firebase Timestamp в datetime"""
    if hasattr(timestamp, 'seconds'):
        return datetime.fromtimestamp(timestamp.seconds + timestamp.nanoseconds / 1e9)
    return timestamp


def format_project_from_firestore(doc_id: str, doc_data: dict) -> FirebaseProject:
    """Преобразует документ Firestore в модель проекта"""
    project = FirebaseProject(
        id=doc_id,
        name=doc_data.get('name', ''),
        description=doc_data.get('description', None),
        owner_id=doc_data.get('owner_id', ''),
        status=doc_data.get('status', 'briefing'),
        briefing_data=doc_data.get('briefing_data', {}),
        created_at=format_firestore_timestamp(doc_data.get('created_at')),
        updated_at=format_firestore_timestamp(doc_data.get('updated_at')) if 'updated_at' in doc_data else None
    )
    return project


def format_chat_message_from_firestore(doc_id: str, doc_data: dict) -> FirebaseChatMessage:
    """Преобразует документ Firestore в модель сообщения чата"""
    message = FirebaseChatMessage(
        id=doc_id,
        project_id=doc_data.get('project_id', ''),
        role=doc_data.get('role', ''),
        content=doc_data.get('content', ''),
        created_at=format_firestore_timestamp(doc_data.get('created_at'))
    )
    return message 