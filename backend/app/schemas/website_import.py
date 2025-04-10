# backend/app/schemas/website_import.py
from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Optional, List, Union # Добавляем Union и validator

class WebsiteImportRequest(BaseModel):
    """Схема для запроса импорта данных с сайта."""
    url: HttpUrl # Используем HttpUrl для валидации URL
    project_id: str # Добавляем ID проекта для связи

class ExpertPortraitData(BaseModel):
    """Структура данных для портрета эксперта."""
    who_is: Optional[str] = Field(None, description="Сфера экспертности")
    sells: Optional[str] = Field(None, description="Продукты/Услуги")
    usp: Optional[str] = Field(None, description="Уникальное Торговое Предложение")
    solves_problem: Optional[str] = Field(None, description="Какую главную проблему решает")

class AudiencePortraitData(BaseModel):
    """Структура данных для портрета ЦА."""
    soc_dem: Optional[str] = Field(None, description="Соцдем (пол, возраст, география, доход...)")
    interests: Optional[str] = Field(None, description="Интересы, образ жизни, увлечения...")
    pains_desires: Optional[str] = Field(None, description="Боли и Желания")
    content_consumed: Optional[str] = Field(None, description="Какой контент смотрят (Тематики)")
    fears_objections: Optional[str] = Field(None, description="Страхи и Возражения (Перед покупкой)")

class CompetitorPortraitData(BaseModel):
    """Структура данных для портрета конкурентов."""
    # Разрешаем строку или список строк
    direct_competitors: Optional[Union[str, List[str]]] = Field(None, description="Прямые конкуренты (Имена, компании)") 
    indirect_competitors: Optional[Union[str, List[str]]] = Field(None, description="Косвенные конкуренты (Альтернативные решения)")

    # Добавляем валидатор, чтобы всегда преобразовывать строку в список из одного элемента
    @validator('direct_competitors', 'indirect_competitors', pre=True, always=True)
    def ensure_list(cls, v):
        if v is None:
            return [] # Возвращаем пустой список, если None
        if isinstance(v, str):
            # Если строка не пустая, возвращаем список с этой строкой, иначе пустой список
            return [v] if v.strip() else [] 
        return v # Если это уже список, возвращаем как есть

class WebsiteImportResponse(BaseModel):
    """Схема для ответа с извлеченными данными."""
    expert_portrait: ExpertPortraitData = Field(default_factory=ExpertPortraitData)
    target_audience_portrait: AudiencePortraitData = Field(default_factory=AudiencePortraitData)
    competitor_portrait: CompetitorPortraitData = Field(default_factory=CompetitorPortraitData)
    # Можно добавить исходный URL для справки
    source_url: Optional[HttpUrl] = None
