from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_sql_db
from app.schemas.user import UserCreate, Token
from app.services import auth, recaptcha

router = APIRouter()

@router.post("/register", response_model=Token)
async def register(user: UserCreate, recaptcha_token: str, db: Session = Depends(get_sql_db)):
    """Регистрация нового пользователя"""
    # Проверяем токен reCAPTCHA
    if not recaptcha.verify_recaptcha_token(recaptcha_token, "REGISTER"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="reCAPTCHA verification failed"
        )
    
    # Создаем пользователя
    db_user = auth.create_user(db, user)
    
    # Создаем токен доступа
    access_token = auth.create_access_token(
        data={"sub": db_user.email}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/token", response_model=Token)
async def login(email: str, password: str, db: Session = Depends(get_sql_db)):
    """Вход пользователя"""
    user = auth.authenticate_user(db, email, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth.create_access_token(
        data={"sub": user.email}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}