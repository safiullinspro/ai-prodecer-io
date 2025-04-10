from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db import get_sql_db
from app.db.models import Project, User
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate, BriefingData
from app.services import auth, gemini

router = APIRouter()

@router.post("/", response_model=ProjectResponse)
async def create_project(project: ProjectCreate, db: Session = Depends(get_sql_db), current_user: User = Depends(auth.get_current_user)):
    """Создание нового проекта"""
    db_project = Project(
        name=project.name,
        description=project.description,
        owner_id=current_user.id,
        status="briefing",
        briefing_data={}
    )
    
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    
    return db_project

@router.get("/", response_model=List[ProjectResponse])
async def get_projects(db: Session = Depends(get_sql_db), current_user: User = Depends(auth.get_current_user)):
    """Получение списка проектов пользователя"""
    projects = db.query(Project).filter(Project.owner_id == current_user.id).all()
    return projects

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, db: Session = Depends(get_sql_db), current_user: User = Depends(auth.get_current_user)):
    """Получение информации о проекте"""
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден"
        )
    
    return project

@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: int, project_update: ProjectUpdate, db: Session = Depends(get_sql_db), current_user: User = Depends(auth.get_current_user)):
    """Обновление информации о проекте"""
    db_project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден"
        )
    
    # Обновляем только предоставленные поля
    update_data = project_update.dict(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_project, key, value)
    
    db.commit()
    db.refresh(db_project)
    
    return db_project

@router.post("/{project_id}/briefing/analyze", response_model=dict)
async def analyze_briefing_info(project_id: int, text: str = Body(..., embed=True), db: Session = Depends(get_sql_db), current_user: User = Depends(auth.get_current_user)):
    """Анализ информации о брифинге с помощью Gemini API"""
    # Проверяем, существует ли проект и принадлежит ли он текущему пользователю
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден"
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
    
    project.briefing_data = briefing_data
    db.commit()
    
    return analysis_result

@router.post("/{project_id}/briefing/questions", response_model=List[str])
async def get_follow_up_questions(project_id: int, db: Session = Depends(get_sql_db), current_user: User = Depends(auth.get_current_user)):
    """Получение уточняющих вопросов на основе текущих данных брифинга"""
    # Проверяем, существует ли проект и принадлежит ли он текущему пользователю
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден"
        )
    
    # Проверяем, есть ли данные брифинга
    if not project.briefing_data:
        return ["Расскажите о вашем продукте или услуге", "Что делает ваше предложение уникальным?", "Как клиенты обычно взаимодействуют с вашим продуктом?"]
    
    # Генерируем уточняющие вопросы на основе текущих данных
    questions = gemini.generate_follow_up_questions(project.briefing_data)
    
    return questions

@router.post("/{project_id}/summarize", response_model=dict)
async def summarize_project(project_id: int, db: Session = Depends(get_sql_db), current_user: User = Depends(auth.get_current_user)):
    """Генерация краткого описания проекта на основе его данных"""
    # Проверяем, существует ли проект и принадлежит ли он текущему пользователю
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден"
        )
    
    # Преобразуем проект в словарь для передачи в сервис
    project_data = {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "briefing_data": project.briefing_data
    }
    
    # Генерируем саммари проекта с помощью Gemini API
    summary_result = gemini.generate_project_summary(project_data)
    
    if summary_result["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при генерации саммари: {summary_result['message']}"
        )
    
    return summary_result