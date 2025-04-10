from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ChatMessageBase(BaseModel):
    """Базовая схема для сообщения чата"""
    role: str = Field(..., description="Роль отправителя сообщения: 'user' или 'assistant'")
    content: str = Field(..., description="Содержание сообщения")


class ChatMessageCreate(ChatMessageBase):
    """Схема для создания сообщения чата"""
    pass


class ChatMessageResponse(ChatMessageBase):
    """Схема для ответа с сообщением чата"""
    id: int
    project_id: int
    created_at: datetime

    class Config:
        orm_mode = True


class ChatHistoryResponse(BaseModel):
    """Схема для ответа с историей чата"""
    messages: List[ChatMessageResponse]

    class Config:
        orm_mode = True