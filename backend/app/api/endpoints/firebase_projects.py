"""
Эндпоинты для работы с проектами через Firebase Firestore.
"""
import logging # Добавляем импорт logging
from fastapi import APIRouter, Depends, HTTPException, status, Body
from typing import List, Dict, Any, Optional
from pydantic import BaseModel # Добавляем импорт BaseModel
from firebase_admin import auth as firebase_auth

from ...dependencies import get_db
from ...db.firebase_models import ProjectCreate, ProjectUpdate, ProjectResponse 
# Импортируем WebsiteImportResponse из правильного места
from ...schemas.website_import import WebsiteImportResponse 
from ...services import firebase_service, gemini
from ...services.firebase_auth import get_current_user
router = APIRouter()
logger = logging.getLogger(__name__) # Инициализируем логгер

@router.post("/", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate, 
    db = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Создание нового проекта"""
    # Создаем данные проекта
    project_data = {
        "name": project.name,
        "description": project.description,
        "owner_id": current_user["uid"],
        "status": "briefing",
        "briefing_data": {
            "utp": "",
            "product_description": "",
            "funnel_elements": [],
            "completion_percentage": 0
        }
    }
    
    # Создаем проект в Firestore
    project_id = await firebase_service.create_project(db, project_data)
    
    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось создать проект"
        )
    
    # Получаем созданный проект
    project = await firebase_service.get_project_by_id(db, project_id)
    
    return project


@router.get("/", response_model=List[ProjectResponse])
async def get_projects(
    db = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Получение списка проектов пользователя"""
    projects = await firebase_service.get_user_projects(db, current_user["uid"])
    return projects


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Получение информации о проекте"""
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
            detail="У вас нет доступа к этому проекту"
        )
    
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_update: ProjectUpdate,
    db = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Обновление информации о проекте"""
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
            detail="У вас нет доступа к этому проекту"
        )
    
    # Обновляем только предоставленные поля
    update_data = {k: v for k, v in project_update.dict(exclude_unset=True).items() if v is not None}
    
    # Обновляем проект в Firestore
    success = await firebase_service.update_project(db, project_id, update_data)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось обновить проект"
        )
    
    # Получаем обновленный проект
    updated_project = await firebase_service.get_project_by_id(db, project_id)
    
    return updated_project


@router.post("/{project_id}/briefing/analyze", response_model=Dict[str, Any])
async def analyze_briefing_info(
    project_id: str,
    text: str = Body(..., embed=True),
    db = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Анализ информации о брифинге с помощью Gemini API"""
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
            detail="У вас нет доступа к этому проекту"
        )
    
    # Анализируем информацию с помощью Gemini API
    analysis_result = gemini.analyze_expert_info(text)
    
    if analysis_result["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при анализе информации: {analysis_result['message']}"
        )
    
    # Обновляем данные брифинга в проекте
    briefing_data = analysis_result["data"]
    briefing_data["completion_percentage"] = analysis_result["completion_percentage"]
    
    # Обновляем проект в Firestore
    await firebase_service.update_project(db, project_id, {"briefing_data": briefing_data})
    
    return analysis_result


@router.post("/{project_id}/briefing/questions", response_model=List[str])
async def get_follow_up_questions(
    project_id: str,
    db = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Получение уточняющих вопросов на основе текущих данных брифинга"""
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
            detail="У вас нет доступа к этому проекту"
        )
    
    # Проверяем, есть ли данные брифинга
    briefing_data = project.get("briefing_data", {})
    if not briefing_data or not isinstance(briefing_data, dict) or not briefing_data.items():
        return ["Расскажите о вашем продукте или услуге", "Что делает ваше предложение уникальным?", "Как клиенты обычно взаимодействуют с вашим продуктом?"]
    
    # Генерируем уточняющие вопросы на основе текущих данных
    questions = gemini.generate_follow_up_questions(briefing_data)
    
    return questions


# Эндпоинт удаления перенесен в main.py


from ...schemas.website_import import CompetitorPortraitData # Импортируем исправленную модель

# --- NEW: Endpoint to save briefing data ---
# Модель для данных брифинга, которые приходят от фронтенда
class BriefingDataUpdate(BaseModel):
    expert_portrait: Optional[Dict[str, Any]] = None
    target_audience_portrait: Optional[Dict[str, Any]] = None
    # Используем исправленную модель CompetitorPortraitData, которая умеет обрабатывать str/list
    competitor_portrait: Optional[CompetitorPortraitData] = None 

@router.put("/{project_id}/briefing", status_code=status.HTTP_204_NO_CONTENT)
async def update_briefing_data(
    project_id: str,
    briefing_update: BriefingDataUpdate, # Используем новую модель для тела запроса
    db = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Обновление данных брифинга для проекта."""
    logger.info(f"Attempting to update briefing data for project {project_id} by user {current_user.get('uid')}")

    # 1. Проверяем доступ к проекту (владелец)
    project_main_data = await firebase_service.get_project_by_id(db, project_id)
    if not project_main_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Проект не найден")
    if project_main_data.get("owner_id") != current_user["uid"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="У вас нет доступа к этому проекту")

    # 2. Подготавливаем данные для обновления (только не None поля)
    # Используем exclude_unset=True, чтобы отправлять только те поля, что пришли в запросе
    update_data = briefing_update.dict(exclude_unset=True) 
    if not update_data:
         # Если пришел пустой объект, ничего не делаем или возвращаем ошибку
         logger.warning(f"Received empty briefing update request for project {project_id}")
         # Можно вернуть 204, если пустое обновление допустимо, или 400
         return None # Возвращаем 204, т.к. технически "обновление" пустого набора данных прошло успешно

    # 3. Вызываем сервис для обновления данных брифинга
    #    Предполагается, что firebase_service.update_briefing_data обновит данные 
    #    (нужно будет создать эту функцию в firebase_service.py)
    #    Важно: Решить, где хранятся данные брифинга - в основном документе или подколлекции.
    #    Судя по get_briefing_data, они в подколлекции 'briefing'.
    success = await firebase_service.update_briefing_data(db, project_id, update_data)

    if not success:
        logger.error(f"Failed to update briefing data for project {project_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось сохранить данные брифинга"
        )

    logger.info(f"Briefing data for project {project_id} updated successfully.")
    # Возвращаем 204 No Content при успехе
    return None
# --- END NEW ---


@router.get("/{project_id}/briefing-data", response_model=WebsiteImportResponse)
async def get_briefing_data(
    project_id: str,
    db = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Получение сохраненных структурированных данных брифинга."""
    logger.info(f"Getting briefing data for project {project_id} by user {current_user.get('uid')}")
    
    # 1. Проверяем доступ к проекту (владелец)
    project_main_data = await firebase_service.get_project_by_id(db, project_id)
    if not project_main_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Проект не найден")
    if project_main_data.get("owner_id") != current_user["uid"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="У вас нет доступа к этому проекту")

    # 2. Получаем данные брифинга из подколлекции
    briefing_data = await firebase_service.get_saved_briefing_data(db, project_id)
    
    if not briefing_data:
        # Если данных нет, возвращаем пустую структуру, соответствующую модели ответа
        logger.info(f"No saved briefing data found for project {project_id}, returning empty response.")
        return WebsiteImportResponse() 
        # Или можно вернуть 404, если это предпочтительнее:
        # raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сохраненные данные брифинга не найдены")

    # 3. Обрабатываем и валидируем данные перед возвратом
    try:
        # Проверяем и преобразуем поля конкурентов, если они сохранены как строки
        competitor_data = briefing_data.get("competitor_portrait", {})
        if isinstance(competitor_data.get("direct_competitors"), str):
            # Преобразуем строку в список (можно добавить логику разделения, если нужно)
            competitor_data["direct_competitors"] = [competitor_data["direct_competitors"]]
        if isinstance(competitor_data.get("indirect_competitors"), str):
            competitor_data["indirect_competitors"] = [competitor_data["indirect_competitors"]]
        
        # Создаем объект ответа Pydantic (теперь типы должны совпадать)
        response_data = WebsiteImportResponse(**briefing_data)
        logger.info(f"Successfully retrieved and validated briefing data for project {project_id}")
        return response_data
    except Exception as e: # Ловим ошибки валидации Pydantic
        logger.error(f"Error creating Pydantic response model from saved data: {e}. Data: {briefing_data}")
        # Возвращаем 500, т.к. данные в БД не соответствуют ожидаемой схеме
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ошибка структуры сохраненных данных брифинга: {e}")
