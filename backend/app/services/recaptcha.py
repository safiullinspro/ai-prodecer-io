import os
import json
import requests
from fastapi import HTTPException, status
from google.cloud import recaptchaenterprise_v1
from google.cloud.recaptchaenterprise_v1 import Assessment

# Константы для reCAPTCHA Enterprise
SITE_KEY = "6LdKMQArAAAAAI6nlaS8z8Ap-Ubp1mqm0guCYhYo"
PROJECT_ID = "yt-producer-ai-1888d"

def verify_recaptcha_token(token: str, action: str = "REGISTER") -> bool:
    """Проверка токена reCAPTCHA Enterprise"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="reCAPTCHA token is required"
        )

    try:
        client = recaptchaenterprise_v1.RecaptchaEnterpriseServiceClient()
        project_name = f"projects/{PROJECT_ID}"

        # Создаем событие оценки
        event = recaptchaenterprise_v1.Event()
        event.site_key = SITE_KEY
        event.token = token
        event.expected_action = action

        assessment = recaptchaenterprise_v1.Assessment()
        assessment.event = event

        request = recaptchaenterprise_v1.CreateAssessmentRequest()
        request.parent = project_name
        request.assessment = assessment

        response = client.create_assessment(request)

        # Проверяем валидность токена
        if not response.token_properties.valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reCAPTCHA token"
            )

        # Проверяем соответствие действия
        if response.token_properties.action != action:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Action mismatch in reCAPTCHA token"
            )

        # Проверяем оценку риска
        return response.risk_analysis.score >= 0.5  # Пороговое значение для определения легитимности запроса

    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify reCAPTCHA token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during reCAPTCHA verification: {str(e)}"
        )