from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime


class BriefingData(BaseModel):
    """Схема для данных брифинга"""
    utp: Optional[str] = Field(None, description="Уникальное торговое предложение")
    product_description: Optional[str] = Field(None, description="Описание продукта/услуги")
    funnel_elements: Optional[List[Dict[str, Any]]] = Field(
        None, 
        description="Элементы продуктовой воронки"
    )
    completion_percentage: Optional[int] = Field(
        0, 
        description="Процент заполнения брифинга",
        ge=0,
        le=100
    )


class ProjectBase(BaseModel):
    """Базовая схема для проекта"""
    name: str
    description: Optional[str] = None
    status: str = "briefing"
    briefing_data: Optional[BriefingData] = None


class ProjectCreate(ProjectBase):
    """Схема для создания проекта"""
    pass


class ProjectUpdate(BaseModel):
    """Схема для обновления проекта"""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    briefing_data: Optional[BriefingData] = None


class ProjectResponse(ProjectBase):
    """Схема для ответа с проектом"""
    id: int
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True