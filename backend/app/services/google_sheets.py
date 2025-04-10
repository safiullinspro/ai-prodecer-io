import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pandas as pd

class GoogleSheetsService:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        
        # Создаем учетные данные из файла
        credentials_path = os.path.join(os.path.dirname(__file__), '../../service-account.json')
        self.credentials = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=self.SCOPES
        )
        
        # Создаем сервис
        self.service = build('sheets', 'v4', credentials=self.credentials)

    def get_spreadsheet_data(self, spreadsheet_id, range_name):
        """Получает данные из указанной таблицы."""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueRenderOption='UNFORMATTED_VALUE',
                dateTimeRenderOption='FORMATTED_STRING'
            ).execute()
            
            values = result.get('values', [])
            if not values:
                return []
                
            # Преобразуем в DataFrame
            df = pd.DataFrame(values[1:], columns=values[0])
            
            # Конвертируем в список словарей
            return df.to_dict('records')
            
        except HttpError as error:
            print(f"An error occurred: {error}")
            raise error

    def get_spreadsheets_list(self):
        """Получает список доступных таблиц."""
        try:
            service = build('drive', 'v3', credentials=self.credentials)
            results = service.files().list(
                q="mimeType='application/vnd.google-apps.spreadsheet'",
                fields="files(id, name)"
            ).execute()
            
            return results.get('files', [])
            
        except Exception as error:
            print(f"An error occurred: {error}")
            return [] 