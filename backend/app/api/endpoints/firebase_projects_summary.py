"""
Маршрут API для получения сводки проекта с использованием Firebase Auth.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Body
from typing import Dict, Any

from ...dependencies import get_db
from ...services import gemini, firebase_service
from ...services.firebase_auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/{project_id}/summarize", response_model=Dict[str, Any])
async def summarize_project(
    project_id: str,
    db = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Генерация краткого описания проекта на основе его данных.
    Требует аутентификацию через Firebase.
    """
    logger.info(f"Запрос на суммаризацию проекта {project_id} от пользователя {current_user.get('uid')}")
    
    try:
        # Получаем проект из Firestore
        project = await firebase_service.get_project_by_id(db, project_id)
        
        if not project:
            logger.warning(f"Попытка получить сводку для несуществующего проекта {project_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Проект не найден"
            )
        
        # Проверяем, принадлежит ли проект текущему пользователю
        if project.get("owner_id") != current_user.get("uid"):
            logger.warning(f"Попытка пользователя {current_user.get('uid')} получить сводку чужого проекта {project_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет прав для получения сводки этого проекта"
            )
        
        # Подготавливаем данные для генерации сводки
        project_data = {
            "id": project.get("id"),
            "name": project.get("name"),
            "description": project.get("description"),
            "status": project.get("status"),
            "briefing_data": project.get("briefing_data", {})
        }
        
        # Генерируем сводку с помощью Gemini API
        summary_result = gemini.generate_project_summary(project_data)
        
        if summary_result.get("status") == "error":
            logger.error(f"Ошибка при генерации сводки для проекта {project_id}: {summary_result.get('message')}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка при генерации сводки: {summary_result.get('message')}"
            )
        
        return summary_result
    
    except HTTPException:
        # Пробрасываем HTTPException дальше
        raise
    except Exception as e:
        logger.exception(f"Непредвиденная ошибка при генерации сводки для проекта {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        ) 