# backend/app/api/endpoints/website_import.py
from fastapi import APIRouter, Depends, HTTPException, Body, Path
from ...schemas.website_import import WebsiteImportRequest, WebsiteImportResponse
# Импортируем сервис и функцию зависимости
from ...services.website_importer_service import WebsiteImporterService, get_website_importer_service
# Импортируем базовые схемы портретов для ответа GET (хотя WebsiteImportResponse их уже содержит)
# from ...schemas.website_import import ExpertPortraitData, AudiencePortraitData, CompetitorPortraitData

router = APIRouter()
TAG = "Website Import"

@router.post(
    "/website-import",
    response_model=WebsiteImportResponse,
    summary="Извлечь и СОХРАНИТЬ данные для брифинга с веб-сайта",
    tags=[TAG]
)
async def import_briefing_from_website(
    request: WebsiteImportRequest = Body(...),
    website_importer: WebsiteImporterService = Depends(get_website_importer_service)
):
    """
    Принимает URL и ID проекта, пытается извлечь данные для портретов
    эксперта, ЦА и конкурентов из текстового содержимого URL с помощью Gemini,
    **сохраняет их в базу данных** и возвращает извлеченные данные.
    """
    try:
        response_data = await website_importer.import_from_url(
            url=str(request.url),
            project_id=request.project_id
        )
        return response_data
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"Unexpected error in /website-import endpoint: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error during website import: {e}")


# --- NEW: GET Endpoint to fetch saved data ---
@router.get(
    "/briefing-data/{project_id}", # Используем префикс /api из main.py, путь будет /api/briefing-data/{project_id}
    response_model=WebsiteImportResponse,
    summary="Получить сохраненные данные брифинга (из импорта)",
    tags=[TAG]
)
async def get_saved_briefing(
    project_id: str = Path(..., title="ID проекта"),
    website_importer: WebsiteImporterService = Depends(get_website_importer_service)
):
    """
    Получает последние сохраненные данные брифинга для указанного проекта,
    которые были получены через импорт с сайта (из документа structured_data).
    """
    try:
        saved_data_dict = await website_importer.get_saved_briefing_data(project_id)
        if saved_data_dict is None:
            # Если данных нет, возвращаем пустую структуру по умолчанию
            print(f"No saved data found for project {project_id}, returning empty response.")
            return WebsiteImportResponse()
        else:
            # Пытаемся создать объект ответа из словаря
            try:
                # Pydantic автоматически сопоставит ключи словаря с полями модели
                # Убедимся, что передаем словарь целиком, а не отдельные портреты
                response_obj = WebsiteImportResponse(**saved_data_dict)
                # Добавляем source_url, если он нужен (хотя он не хранится в БД)
                # response_obj.source_url = saved_data_dict.get("source_url") # Пример
                print(f"Returning saved data for project {project_id}")
                return response_obj
            except Exception as pydantic_error:
                print(f"Error creating Pydantic response model from saved data: {pydantic_error}. Data: {saved_data_dict}")
                # В случае ошибки парсинга сохраненных данных, возвращаем пустую структуру
                return WebsiteImportResponse()
    except Exception as e:
        print(f"Unexpected error in /briefing-data/{project_id} endpoint: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error fetching saved briefing data: {e}")
# --- END NEW ---
