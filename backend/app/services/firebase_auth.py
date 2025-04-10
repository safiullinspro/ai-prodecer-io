"""
Сервис аутентификации с использованием Firebase Auth.
"""
import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from fastapi import Depends, HTTPException, status, Header
from typing import Dict, Any, Optional
import logging
import traceback

logger = logging.getLogger(__name__)

def verify_firebase_token(token: str) -> Dict[str, Any]:
    """
    Проверяет токен Firebase и возвращает декодированные данные пользователя
    """
    try:
        logger.info(f"Начинаем проверку токена Firebase (первые 10 символов: {token[:10]}...)")
        
        # Проверяем токен
        decoded_token = firebase_auth.verify_id_token(token)
        
        # Получаем пользователя по UID из токена
        uid = decoded_token.get('uid')
        if not uid:
            logger.error("В декодированном токене отсутствует uid")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительный токен авторизации (отсутствует uid)"
            )
            
        logger.info(f"Получаем пользователя для uid: {uid}")
        user = firebase_auth.get_user(uid)
        
        logger.info(f"Пользователь найден: {user.uid}, email: {user.email}")
        
        # Формируем данные пользователя
        user_data = {
            "uid": user.uid,
            "email": user.email,
            "display_name": user.display_name,
            "photo_url": user.photo_url,
            "provider_id": user.provider_id,
            "email_verified": user.email_verified
        }
        
        return user_data
    except firebase_auth.InvalidIdTokenError as e:
        logger.error(f"Недействительный токен: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Недействительный токен авторизации: {str(e)}"
        )
    except firebase_auth.ExpiredIdTokenError as e:
        logger.error(f"Токен истек: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Истек срок действия токена авторизации: {str(e)}"
        )
    except firebase_auth.RevokedIdTokenError as e:
        logger.error(f"Токен отозван: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Токен авторизации отозван: {str(e)}"
        )
    except firebase_auth.UserNotFoundError as e:
        logger.error(f"Пользователь не найден: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Пользователь не найден: {str(e)}"
        )
    except firebase_auth.CertificateFetchError as e:
        logger.error(f"Ошибка получения сертификатов: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка сервера при проверке токена: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Ошибка при верификации токена Firebase: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Ошибка авторизации: {str(e)}"
        )

async def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    FastAPI зависимость для получения текущего аутентифицированного пользователя
    """
    if not authorization:
        logger.warning("Отсутствует заголовок Authorization")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Отсутствует токен авторизации",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Проверяем формат Authorization: Bearer <token>
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.warning(f"Неверный формат токена: {authorization[:15]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный формат токена авторизации. Используйте формат 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Получаем токен
    token = parts[1]
    
    # Проверяем токен и получаем данные пользователя
    return verify_firebase_token(token)

async def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[Dict[str, Any]]:
    """
    FastAPI зависимость для получения текущего пользователя, если он аутентифицирован,
    или None, если пользователь не аутентифицирован.
    """
    if not authorization:
        return None
    
    try:
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        
        token = parts[1]
        return verify_firebase_token(token)
    except HTTPException:
        return None
    except Exception as e:
        logger.warning(f"Ошибка при получении опционального пользователя: {e}")
        return None 