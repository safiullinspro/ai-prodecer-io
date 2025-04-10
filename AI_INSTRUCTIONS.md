# Инструкция по работе с кодом проекта YT Producer AI

Эта инструкция предназначена для ИИ-ассистентов, которые будут работать с кодовой базой проекта YT Producer AI.

## 1. Изучение проекта

### Общая структура проекта
- Проект разделен на две основные части: `frontend` (React) и `backend` (FastAPI).
- Используется PostgreSQL в качестве базы данных.
- Компоненты запускаются в Docker-контейнерах через docker-compose.

### Основные каталоги и их назначение:
- `frontend/` - клиентское React-приложение
  - `src/components/` - компоненты React
  - `src/pages/` - страницы приложения
  - `src/services/` - сервисы для работы с API
  - `src/utils/` - вспомогательные функции
  
- `backend/` - API на FastAPI 
  - `app/api/endpoints/` - эндпоинты API
  - `app/db/` - модели базы данных и настройки подключения
  - `app/schemas/` - схемы данных для валидации с помощью Pydantic
  - `app/services/` - бизнес-логика
  - `app/utils/` - вспомогательные функции

## 2. Работа с кодом

### Изучение кода

1. **Сначала изучи структуру проекта и документацию**:
   ```
   list_dir /
   read_file PROJECT_OVERVIEW.md
   read_file PROJECT_STRUCTURE.md
   read_file roadmap.md
   read_file roadmap_timeline.md
   ```

2. **Поиск нужных компонентов**:
   ```
   codebase_search "название компонента или функции"
   ```

3. **Поиск файлов**:
   ```
   file_search "часть имени файла"
   ```

4. **Чтение содержимого файла**:
   ```
   read_file путь/к/файлу.js
   ```

### Редактирование файлов

1. **Редактирование существующего файла**:
   ```
   edit_file target_file="путь/к/файлу.js" instructions="Что я собираюсь изменить" code_edit="... код с изменениями ..."
   ```

2. **Создание нового файла**:
   ```
   edit_file target_file="путь/к/новому/файлу.js" instructions="Создаю новый файл" code_edit="... содержимое файла ..."
   ```

### Именование и стили кода

1. **React-компоненты**:
   - Используй функциональные компоненты с хуками
   - Используй Material UI для стилизации
   - Файлы компонентов называй с заглавной буквы

2. **Python-код**:
   - Следуй PEP 8
   - Используй типизацию
   - Комментируй сложные участки кода
   - Для методов API используй snake_case
   - Для классов используй CamelCase

## 3. Пример процесса работы с кодом

### Пример 1: Добавление нового поля в модель

1. **Изучение модели**:
   ```
   codebase_search "модель Project"
   read_file backend/app/db/models.py
   ```

2. **Обновление модели**:
   ```
   edit_file target_file="backend/app/db/models.py" instructions="Добавляю поле keywords в модель Project" code_edit="class Project(Base):
       ...
       name = Column(String(255), nullable=False)
       description = Column(String, nullable=True)
       keywords = Column(String(500), nullable=True)  # Новое поле
       ...
   "
   ```

3. **Обновление схемы**:
   ```
   read_file backend/app/schemas/project.py
   edit_file target_file="backend/app/schemas/project.py" instructions="Добавляю поле keywords в схему Project" code_edit="class ProjectBase(BaseModel):
       name: str
       description: Optional[str] = None
       keywords: Optional[str] = None  # Новое поле
   "
   ```

### Пример 2: Создание нового сервиса

1. **Создание файла сервиса**:
   ```
   edit_file target_file="backend/app/services/ai_service.py" instructions="Создаю новый файл сервиса для работы с AI" code_edit="import os
   import logging
   from typing import List, Optional, Dict, Any
   
   class AIService:
       @staticmethod
       def some_method():
           # Реализация метода
           pass
   "
   ```

2. **Интеграция сервиса в API**:
   ```
   read_file backend/app/api/endpoints/some_endpoint.py
   edit_file target_file="backend/app/api/endpoints/some_endpoint.py" instructions="Интегрирую AIService в API" code_edit="from app.services.ai_service import AIService
   
   @router.post('/analyze')
   def analyze_something():
       result = AIService.some_method()
       return result
   "
   ```

### Пример 3: Обновление фронтенда

1. **Добавление поля в форму**:
   ```
   read_file frontend/src/pages/SomePage.jsx
   edit_file target_file="frontend/src/pages/SomePage.jsx" instructions="Добавляю поле keywords в форму" code_edit="
   <TextField
     name='keywords'
     label='Ключевые слова'
     value={formData.keywords}
     onChange={handleChange}
     fullWidth
     margin='normal'
   />
   "
   ```

2. **Обновление вызова API**:
   ```
   read_file frontend/src/services/api.js
   edit_file target_file="frontend/src/services/api.js" instructions="Обновляю метод createProject для передачи ключевых слов" code_edit="
   createProject: (projectData) => handleApiResponse(apiClient.post('/projects', {
     name: projectData.name,
     description: projectData.description,
     keywords: projectData.keywords  // Добавляем ключевые слова
   })),
   "
   ```

## 4. Работа с функционалом ИИ

### Интеграция с Google Gemini API

1. **Настройка API**:
   - Убедись, что в `requirements.txt` есть `google-generativeai>=0.3.0`
   - API-ключ берется из переменных окружения `GOOGLE_API_KEY`

2. **Использование API**:
   ```python
   import google.generativeai as genai
   
   genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", ""))
   model = genai.GenerativeModel(model_name='gemini-1.0-pro')
   response = model.generate_content("Ваш промпт")
   ```

## 5. Полезные советы

1. **Всегда учитывай существующие паттерны в коде**. Не изобретай свои подходы, а следуй тому, что уже используется в проекте.

2. **Проверяй зависимости**. Если добавляешь новый функционал, убедись, что необходимые библиотеки указаны в `requirements.txt`.

3. **Придерживайся архитектуры проекта**:
   - Бизнес-логика должна быть в сервисах, а не в API-эндпоинтах
   - API-эндпоинты отвечают только за валидацию и вызов сервисов
   - Модели описывают структуру БД
   - Схемы отвечают за валидацию входных/выходных данных

4. **Обрабатывай ошибки**. Используй try-except и возвращай понятные сообщения об ошибках.

5. **Добавляй логирование**. Используй стандартный модуль `logging`.

6. **Документируй код**. Добавляй комментарии и используй docstrings для методов.

## 6. Интеграция новых скриптов парсинга

При интеграции парсинг-скриптов в API, следуй этим принципам:

1. Выдели основную логику скрипта в функции без побочных эффектов
2. Создай асинхронные методы в сервисе `parser_service.py`
3. Используй фоновые задачи для длительных операций
4. Обновляй статус парсинга в базе данных
5. Возвращай результаты через API с понятными сообщениями

## 7. Вывод

Следуя этим инструкциям, ты сможешь эффективно работать с кодовой базой проекта YT Producer AI, поддерживая единый стиль кода и архитектурные принципы. Приоритеты в разработке должны соответствовать roadmap.md и roadmap_timeline.md, а все изменения должны стремиться к созданию масштабируемого, поддерживаемого и безопасного кода. 