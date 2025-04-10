# backend/app/services/website_importer_service.py
import os
import json
import re
import requests
import traceback
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional
import google.generativeai as genai
from google.generativeai import types
from fastapi import HTTPException, Depends # Добавляем Depends
from dotenv import load_dotenv
from google.cloud import firestore as google_firestore # Добавляем импорт Firestore

# Импортируем новые схемы для ответа
from ..schemas.website_import import WebsiteImportResponse
# Импортируем зависимость для БД
from ..dependencies import get_db

load_dotenv()

# Конфигурация Gemini (глобальная)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
generation_config = {
    "temperature": 0.2, # Изменено на 0.2
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 65535, # Изменено на 65535
}
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

# Промпт для извлечения данных
EXTRACTION_PROMPT_TEMPLATE = """
Проанализируй следующий текст, извлеченный с веб-сайта. Твоя задача — извлечь как можно больше информации об эксперте (владельце сайта), его целевой аудитории и конкурентах, и структурировать ее в JSON-объект ТОЧНО следующего формата. Не добавляй никаких комментариев, пояснений или приветствий. Верни ТОЛЬКО JSON-объект или слово "ERROR", если извлечь данные невозможно.

Структура JSON:
```json
{{
  "expert_portrait": {{
    "who_is": null,
    "sells": null,
    "usp": null,
    "solves_problem": null
  }},
  "target_audience_portrait": {{
    "soc_dem": null,
    "interests": null,
    "pains_desires": null,
    "content_consumed": null,
    "fears_objections": null
  }},
  "competitor_portrait": {{
    "direct_competitors": null,
    "indirect_competitors": null
  }}
}}
```
Заполняй значения ключей извлеченной информацией из текста.
**Важно:** Если информация для какого-либо ключа (особенно для `direct_competitors` и `indirect_competitors`) отсутствует в тексте, **не оставляй значение `null`**, а **сгенерируй наиболее вероятные предположения**, основываясь на сфере деятельности эксперта, его продуктах/услугах и целевой аудитории. Например, для клиники инфузионной терапии в Москве предположи другие подобные клиники или смежные услуги.

Текст для анализа:
---
{website_text}
---

Результат (ТОЛЬКО JSON или слово ERROR):
"""

class WebsiteImporterService:
    """
    Сервис для импорта данных брифинга с веб-сайта с использованием Gemini.
    """
    def __init__(self, db: google_firestore.AsyncClient): # Принимаем db
        self.db = db # Сохраняем db
        self.model = None
        if not GEMINI_API_KEY:
            print("Ошибка: GEMINI_API_KEY не установлен для WebsiteImporterService.")
            return # Выходим, если ключа нет
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            # Используем модель по умолчанию из api_setup или указываем явно
            from ..core.api_setup import get_gemini_model
            self.model = get_gemini_model() # Получаем модель (например, 'gemini-1.5-flash-latest')
            if not self.model:
                 raise ValueError("Не удалось получить модель Gemini из api_setup")
            print("WebsiteImporterService initialized with Gemini model.")
        except Exception as e:
            print(f"Ошибка инициализации модели Gemini в WebsiteImporterService: {e}")
            self.model = None

    async def _extract_data_with_gemini(self, text_input: str) -> Optional[Dict[str, Any]]:
        """
        Внутренний метод для вызова Gemini и парсинга JSON ответа.
        """
        if not self.model:
            error_message = "Gemini model not initialized in WebsiteImporterService."
            print(error_message)
            raise HTTPException(status_code=500, detail=error_message)

        print("Attempting to generate brief from text using Gemini...")
        extraction_prompt = EXTRACTION_PROMPT_TEMPLATE.format(website_text=text_input)

        try:
            # Создаем объект types.GenerationConfig из глобального словаря
            try:
                gen_config_object = types.GenerationConfig(**generation_config)
            except Exception as config_error:
                 error_message = f"Failed to create GenerationConfig object: {config_error}"
                 print(error_message)
                 raise HTTPException(status_code=500, detail=error_message)

            # Вызов API
            response = await self.model.generate_content_async(
                extraction_prompt,
                generation_config=gen_config_object,
                safety_settings=safety_settings
            )
            response_text = response.text.strip()
            print(f"Raw response from Gemini: {response_text[:500]}...") # Логируем начало ответа

            if response_text.upper() == "ERROR":
                print("LLM indicated ERROR during extraction.")
                raise HTTPException(status_code=400, detail="LLM indicated it could not extract data (returned ERROR).")

            # Попытка парсинга JSON
            json_match = re.search(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL)
            json_string_to_parse = ""
            if json_match:
                json_string_to_parse = json_match.group(1)
            elif response_text.startswith("{") and response_text.endswith("}"):
                 json_string_to_parse = response_text
            else:
                 print(f"Gemini response is not JSON or ERROR. Raw response: {response_text}")
                 raise HTTPException(status_code=500, detail=f"LLM response was not in the expected JSON format or ERROR. Raw response: {response_text}")

            try:
                print(f"Attempting to parse JSON string: {json_string_to_parse}")
                extracted_data = json.loads(json_string_to_parse)
                print(f"Successfully parsed JSON from Gemini: {extracted_data}")

                # Проверка базовой структуры
                if not isinstance(extracted_data, dict) or "expert_portrait" not in extracted_data:
                     print(f"Extracted data structure mismatch (expected 'expert_portrait'): {extracted_data}")
                     raise HTTPException(status_code=500, detail=f"LLM response structure mismatch. Expected 'expert_portrait' key. Got: {extracted_data}")

                return extracted_data

            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from Gemini response: {e}. String was: {json_string_to_parse}")
                raise HTTPException(status_code=500, detail=f"Failed to decode JSON from LLM response. Raw response: {json_string_to_parse}")

        except Exception as e:
            error_message = f"Error calling Gemini API for extraction: {e}"
            print(error_message)
            print(f"Traceback: {traceback.format_exc()}")
            # Перевыбрасываем как HTTPException, чтобы ошибка дошла до клиента
            raise HTTPException(status_code=500, detail=error_message)


    async def import_from_url(self, url: str, project_id: str) -> WebsiteImportResponse:
        """
        Основной метод: скачивает URL, извлекает текст, вызывает Gemini,
        сохраняет результат в Firestore и возвращает структурированные данные.
        """
        print(f"Starting website import for URL: {url}, Project ID: {project_id}")
        try:
            # 1. Скачивание и парсинг текста
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(str(url), headers=headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            for script_or_style in soup(["script", "style", "nav", "footer", "header"]):
                script_or_style.decompose()
            text_content = ' '.join(soup.stripped_strings)

            if not text_content:
                print("Could not extract text content from the URL.")
                raise HTTPException(status_code=400, detail="Could not extract meaningful text content from the URL.")

            print(f"Extracted text (first 500 chars): {text_content[:500]}...")

            # 2. Извлечение данных с помощью Gemini
            extracted_data = await self._extract_data_with_gemini(text_content)

            if not extracted_data:
                 raise HTTPException(status_code=500, detail="Extraction process failed unexpectedly after Gemini call.")

            # 3. Формирование объекта ответа
            try:
                # Преобразуем строки конкурентов в списки, если необходимо (перед валидацией Pydantic)
                competitor_data = extracted_data.get("competitor_portrait", {})
                if isinstance(competitor_data.get("direct_competitors"), str):
                    competitor_data["direct_competitors"] = [competitor_data["direct_competitors"]]
                if isinstance(competitor_data.get("indirect_competitors"), str):
                    competitor_data["indirect_competitors"] = [competitor_data["indirect_competitors"]]
                
                response_data = WebsiteImportResponse(
                    expert_portrait=extracted_data.get("expert_portrait", {}),
                    target_audience_portrait=extracted_data.get("target_audience_portrait", {}),
                    competitor_portrait=competitor_data, # Используем обработанные данные
                    source_url=url
                )
                print("Successfully created WebsiteImportResponse object.")
            except Exception as pydantic_error:
                 print(f"Error creating Pydantic response model: {pydantic_error}. Data was: {extracted_data}")
                 raise HTTPException(status_code=500, detail=f"Failed to structure extracted data: {pydantic_error}")

            # 4. Сохранение в Firestore
            try:
                doc_ref = self.db.collection("projects").document(project_id).collection("briefing").document("structured_data")
                await doc_ref.set(response_data.dict(exclude={'source_url'}), merge=False) # Перезаписываем документ
                print(f"Successfully saved imported data to Firestore for project {project_id}")
            except Exception as db_error:
                print(f"Error saving imported data to Firestore for project {project_id}: {db_error}")
                raise HTTPException(status_code=500, detail=f"Failed to save imported data to database: {db_error}")

            return response_data # Возвращаем данные после успешного сохранения

        except requests.exceptions.RequestException as req_err:
            print(f"Error fetching URL {url}: {req_err}")
            raise HTTPException(status_code=400, detail=f"Could not fetch content from URL: {req_err}")
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            print(f"Unexpected error during website import: {e}")
            print(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Unexpected server error during website import: {e}")

    async def get_saved_briefing_data(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Получает сохраненные данные брифинга (structured_data) из Firestore.
        """
        print(f"WebsiteImporterService getting saved briefing for project {project_id}")
        try:
            doc_ref = self.db.collection("projects").document(project_id).collection("briefing").document("structured_data")
            doc_snapshot = await doc_ref.get()
            if doc_snapshot.exists:
                print(f"Saved briefing data found for project {project_id}")
                return doc_snapshot.to_dict()
            else:
                print(f"Saved briefing data not found for project {project_id}")
                return None
        except Exception as e:
            print(f"Error getting saved briefing data for project {project_id} from Firestore: {e}")
            return None # Возвращаем None при ошибке чтения, чтобы фронтенд показал пустые поля

# --- NEW: Dependency Injection Factory ---
def get_website_importer_service(db: google_firestore.AsyncClient = Depends(get_db)) -> WebsiteImporterService:
    """FastAPI dependency to get WebsiteImporterService instance with DB."""
    return WebsiteImporterService(db=db)
# --- END NEW ---
