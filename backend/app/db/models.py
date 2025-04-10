from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Отношение к проектам
    projects = relationship("Project", back_populates="owner")


class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Статус проекта
    status = Column(String, default="briefing")
    
    # Данные брифинга
    briefing_data = Column(JSON, nullable=True)
    
    # Отношение к пользователю
    owner = relationship("User", back_populates="projects")
    
    # Отношение к сообщениям чата
    chat_messages = relationship("ChatMessage", back_populates="project")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    role = Column(String)  # 'user' или 'assistant'
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Отношение к проекту
    project = relationship("Project", back_populates="chat_messages")