from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..services.google_sheets import GoogleSheetsService
from googleapiclient.errors import HttpError

router = APIRouter(prefix="/google", tags=["google"])
sheets_service = GoogleSheetsService()

class ImportRequest(BaseModel):
    spreadsheet_id: str
    sheet_name: str = "ВИДЕО"  # По умолчанию используем вкладку ВИДЕО

@router.get("/auth")
async def get_auth_url():
    """Получает URL для авторизации в Google."""
    auth_url = sheets_service.get_auth_url()
    return {"auth_url": auth_url}

@router.get("/callback")
async def auth_callback(code: str):
    """Обрабатывает callback от Google OAuth."""
    sheets_service.set_credentials(code)
    return {"status": "success"}

@router.get("/spreadsheets")
async def list_spreadsheets():
    """Получает список доступных таблиц."""
    if not sheets_service.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    spreadsheets = sheets_service.get_spreadsheets_list()
    return spreadsheets

@router.post("/import")
async def import_spreadsheet(request: ImportRequest):
    """Импорт данных из выбранной таблицы."""
    try:
        data = sheets_service.get_spreadsheet_data(
            request.spreadsheet_id,
            f"{request.sheet_name}!A1:Z1000"
        )
        
        if not data:
            raise HTTPException(status_code=404, detail="No data found")
            
        return {"status": "success", "data": data}
    except HttpError as e:
        if "PERMISSION_DENIED" in str(e):
            raise HTTPException(
                status_code=403, 
                detail="Нет доступа к таблице. Убедитесь, что вы предоставили доступ сервисному аккаунту yt-producer-app@yt-producer-ai.iam.gserviceaccount.com"
            )
        elif "SERVICE_DISABLED" in str(e):
            raise HTTPException(
                status_code=400,
                detail="Google Sheets API не включен. Включите его в Google Cloud Console."
            )
        else:
            raise HTTPException(status_code=400, detail=str(e)) 