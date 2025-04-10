"""
Сервис для работы с Firebase Firestore.
Предоставляет функции для работы с коллекциями и документами Firestore.
"""
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from google.cloud import firestore
from firebase_admin import firestore as admin_firestore
from ..db.firebase_models import (
    FirebaseProject, 
    FirebaseChatMessage, 
    FirebaseUser,
    format_project_from_firestore,
    format_chat_message_from_firestore
)

logger = logging.getLogger(__name__)

# --- Общие функции ---

async def get_document_by_id(db: firestore.AsyncClient, collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
    """Получить документ по ID"""
    try:
        doc_ref = db.collection(collection).document(doc_id)
        doc = await doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        logger.error(f"Error getting saved briefing data for project {project_id}: {e}")
        return None

async def update_briefing_data(db: firestore.AsyncClient, project_id: str, update_data: Dict[str, Any]) -> bool:
    """
    Обновляет данные брифинга в документе 'structured_data' подколлекции 'briefing'.
    Использует set с merge=True для обновления только переданных полей.
    """
    logger.info(f"Updating briefing data for project {project_id} in briefing/structured_data...")
    if not update_data:
        logger.warning(f"No briefing data provided to update for project {project_id}.")
        return True # Считаем успешным, т.к. нечего обновлять

    # Убедимся, что обновляем только разрешенные поля брифинга
    # (Хотя set(merge=True) сам справится, но для ясности оставим)
    allowed_keys = {"expert_portrait", "target_audience_portrait", "competitor_portrait"}
    data_to_update = {k: v for k, v in update_data.items() if k in allowed_keys}

    if not data_to_update:
        logger.warning(f"No valid briefing fields found in update_data for project {project_id}.")
        return True # Считаем успешным, т.к. нечего обновлять

    try:
        # Путь к документу с данными брифинга, как на скриншоте
        briefing_doc_ref = db.collection("projects").document(project_id).collection("briefing").document("structured_data")
        
        # Используем set с merge=True для обновления или создания документа/полей
        await briefing_doc_ref.set(data_to_update, merge=True)
        
        logger.info(f"Briefing data for project {project_id} updated successfully in briefing/structured_data.")
        return True
    except Exception as e:
        logger.error(f"Error updating briefing data for project {project_id} in briefing/structured_data: {e}")
        logger.exception(e) # Логируем полный traceback
        return False


async def add_document(db: firestore.AsyncClient, collection: str, data: Dict[str, Any], doc_id: Optional[str] = None) -> Optional[str]:
    """Добавить документ в коллекцию"""
    try:
        if doc_id:
            doc_ref = db.collection(collection).document(doc_id)
            await doc_ref.set(data)
            return doc_id
        else:
            # Автоматически генерируем ID
            doc_ref = db.collection(collection).document()
            await doc_ref.set(data)
            return doc_ref.id
    except Exception as e:
        logger.error(f"Ошибка при добавлении документа в {collection}: {e}")
        return None


async def update_document(db: firestore.AsyncClient, collection: str, doc_id: str, data: Dict[str, Any]) -> bool:
    """Обновить документ"""
    try:
        doc_ref = db.collection(collection).document(doc_id)
        await doc_ref.update(data)
        return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении документа {collection}/{doc_id}: {e}")
        return False


async def delete_document(db: firestore.AsyncClient, collection: str, doc_id: str) -> bool:
    """Удалить документ"""
    try:
        doc_ref = db.collection(collection).document(doc_id)
        await doc_ref.delete()
        return True
    except Exception as e:
        logger.error(f"Ошибка при удалении документа {collection}/{doc_id}: {e}")
        return False


async def query_collection(
    db: firestore.AsyncClient, 
    collection: str, 
    field_filters: List[tuple] = None,
    order_by: str = None,
    direction: str = "ASCENDING",
    limit: int = None
) -> List[Dict[str, Any]]:
    """Выполнить запрос к коллекции с фильтрами

    Args:
        db: Клиент Firestore
        collection: Название коллекции
        field_filters: Список фильтров в формате [(поле, оператор, значение), ...]
        order_by: Поле для сортировки
        direction: Направление сортировки ("ASCENDING" или "DESCENDING")
        limit: Ограничение количества результатов

    Returns:
        Список документов
    """
    try:
        query = db.collection(collection)
        
        # Применяем фильтры
        if field_filters:
            for field, op, value in field_filters:
                query = query.where(field, op, value)
        
        # Применяем сортировку
        if order_by:
            if direction == "DESCENDING":
                query = query.order_by(order_by, direction=firestore.Query.DESCENDING)
            else:
                query = query.order_by(order_by)
        
        # Применяем лимит
        if limit:
            query = query.limit(limit)
        
        # Выполняем запрос
        docs = await query.get()
        
        # Формируем результат
        result = []
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data["id"] = doc.id
            result.append(doc_data)
        
        return result
    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса к коллекции {collection}: {e}")
        return []


# --- Функции для работы с пользователями ---

async def get_user_by_id(db: firestore.AsyncClient, user_id: str) -> Optional[FirebaseUser]:
    """Получить пользователя по ID"""
    user_data = await get_document_by_id(db, "users", user_id)
    if user_data:
        user_data["uid"] = user_id
        return user_data
    return None


async def get_user_by_email(db: firestore.AsyncClient, email: str) -> Optional[FirebaseUser]:
    """Получить пользователя по email"""
    try:
        users = await query_collection(db, "users", [("email", "==", email)])
        if users and len(users) > 0:
            return users[0]
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении пользователя по email {email}: {e}")
        return None


async def create_user(db: firestore.AsyncClient, user_data: Dict[str, Any], user_id: str) -> Optional[str]:
    """Создать нового пользователя"""
    user_data["created_at"] = datetime.now()
    user_data["is_active"] = True
    return await add_document(db, "users", user_data, user_id)


async def update_user(db: firestore.AsyncClient, user_id: str, user_data: Dict[str, Any]) -> bool:
    """Обновить данные пользователя"""
    user_data["updated_at"] = datetime.now()
    return await update_document(db, "users", user_id, user_data)


# --- Функции для работы с проектами ---

async def get_project_by_id(db: firestore.AsyncClient, project_id: str) -> Optional[FirebaseProject]:
    """Получить проект по ID"""
    project_data = await get_document_by_id(db, "projects", project_id)
    if project_data:
        return format_project_from_firestore(project_id, project_data)
    return None


async def get_user_projects(db: firestore.AsyncClient, user_id: str) -> List[FirebaseProject]:
    """Получить все проекты пользователя"""
    try:
        projects = await query_collection(
            db, 
            "projects", 
            [("owner_id", "==", user_id)],
            order_by="created_at",
            direction="DESCENDING"
        )
        
        return [format_project_from_firestore(project["id"], project) for project in projects]
    except Exception as e:
        logger.error(f"Ошибка при получении проектов пользователя {user_id}: {e}")
        return []


async def create_project(db: firestore.AsyncClient, project_data: Dict[str, Any]) -> Optional[str]:
    """Создать новый проект"""
    project_data["created_at"] = datetime.now()
    project_data["status"] = project_data.get("status", "briefing")
    project_data["briefing_data"] = project_data.get("briefing_data", {
        "utp": "",
        "product_description": "",
        "funnel_elements": [],
        "completion_percentage": 0
    })
    
    return await add_document(db, "projects", project_data)


async def update_project(db: firestore.AsyncClient, project_id: str, project_data: Dict[str, Any]) -> bool:
    """Обновить проект"""
    project_data["updated_at"] = datetime.now()
    return await update_document(db, "projects", project_id, project_data)


async def delete_project(db: firestore.AsyncClient, project_id: str) -> bool:
    """Удалить проект"""
    # Получаем все сообщения чата проекта
    chat_messages = await query_collection(db, "chat_messages", [("project_id", "==", project_id)])
    
    # Удаляем все сообщения чата
    for message in chat_messages:
        await delete_document(db, "chat_messages", message["id"])
    
    # Удаляем сам проект
    return await delete_document(db, "projects", project_id)


# --- Функции для работы с сообщениями чата ---

async def get_project_chat_messages(db: firestore.AsyncClient, project_id: str) -> List[FirebaseChatMessage]:
    """Получить все сообщения чата для проекта"""
    try:
        messages = await query_collection(
            db, 
            "chat_messages", 
            [("project_id", "==", project_id)],
            order_by="created_at"
        )
        
        return [format_chat_message_from_firestore(message["id"], message) for message in messages]
    except Exception as e:
        logger.error(f"Ошибка при получении сообщений чата для проекта {project_id}: {e}")
        return []


async def add_chat_message(db: firestore.AsyncClient, message_data: Dict[str, Any]) -> Optional[str]:
    """Добавить сообщение в чат"""
    message_data["created_at"] = datetime.now()
    return await add_document(db, "chat_messages", message_data)


# --- Синхронные функции для использования в фоновых задачах ---

def sync_get_document_by_id(db: admin_firestore.client, collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
    """Синхронная версия для получения документа по ID"""
    try:
        doc_ref = db.collection(collection).document(doc_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении документа {collection}/{doc_id}: {e}")
        return None


def sync_update_document(db: admin_firestore.client, collection: str, doc_id: str, data: Dict[str, Any]) -> bool:
    """Синхронная версия для обновления документа"""
    try:
        doc_ref = db.collection(collection).document(doc_id)
        doc_ref.update(data)
        return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении документа {collection}/{doc_id}: {e}")
        return False
