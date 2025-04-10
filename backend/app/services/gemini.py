import os
import google.generativeai as genai
from typing import Dict, Any, Optional, List
from fastapi import HTTPException
import logging
import json
import re
# Импортируем функцию для получения модели из центральной конфигурации
from ..core.api_setup import get_gemini_model

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Константы - MODEL_NAME больше не нужен для основных функций
# API_KEY = os.environ.get("GEMINI_API_KEY")
# MODEL_NAME = "gemini-2.0-flash-exp" # Убираем или оставляем только для теста

# Инициализация Gemini API - Эта функция больше не нужна, т.к. инициализация происходит в api_setup.py
# def init_gemini():
#     """Инициализирует Gemini API с API ключом из переменных окружения"""
#     try:
#         if not API_KEY:
#             raise ValueError("GEMINI_API_KEY не найден в переменных окружения")
#         genai.configure(api_key=API_KEY)
#         logger.info("Google Gemini API инициализирован успешно")
#         return True
#     except Exception as e:
#         logger.error(f"Ошибка при инициализации Gemini API: {e}")
#         return False

# Тестирование подключения к Gemini API
def test_gemini_connection() -> Dict[str, Any]:
    """Инициализирует Gemini API с API ключом из переменных окружения"""
    try:
        if not API_KEY:
            raise ValueError("GEMINI_API_KEY не найден в переменных окружения")
            
        genai.configure(api_key=API_KEY)
        logger.info("Google Gemini API инициализирован успешно")
        return True
    except Exception as e:
        logger.error(f"Ошибка при инициализации Gemini API: {e}")
        return False

# Тестирование подключения к Gemini API
    """Тестирует подключение к Gemini API, используя модель по умолчанию"""
    try:
        # Получаем модель по умолчанию
        model = get_gemini_model()
        if not model:
             raise ValueError("Не удалось получить модель Gemini из api_setup для теста.")
        response = model.generate_content("Привет, это тестовое сообщение для проверки подключения к Gemini API.")
        return {"status": "success", "message": response.text}
    except Exception as e:
        logger.error(f"Ошибка при тестировании подключения к Gemini API: {e}")
        return {"status": "error", "message": str(e)}

# Анализ информации о пользователе и его продукте
def analyze_expert_info(text: str, chat_history: List[Dict[str, str]] = None, current_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Анализирует информацию об эксперте и его продукте с учетом контекста чата и текущих данных
    
    Args:
        text: Текст сообщения пользователя
        chat_history: История диалога (последние сообщения)
        current_data: Текущие данные брифинга (если есть)
    
    Returns:
        Dict: Результат анализа с обновленными данными
    """
    try:
        # Получаем модель по умолчанию
        model = get_gemini_model()
        if not model:
             logger.error("Не удалось получить модель Gemini для analyze_expert_info.")
             # Возвращаем ошибку или используем запасной вариант
             return {"status": "error", "message": "Модель Gemini недоступна"}

        # Преобразуем текущие данные в строку контекста
        current_context = ""
        if current_data:
            current_context = "\nТекущие данные брифинга:\n"
            
            if current_data.get("utp"):
                current_context += f"УТП: {current_data['utp']}\n"
            else:
                current_context += "УТП: Не заполнено\n"
            
            if current_data.get("product_description"):
                current_context += f"Описание продукта: {current_data['product_description']}\n"
            else:
                current_context += "Описание продукта: Не заполнено\n"
            
            if current_data.get("funnel_elements") and len(current_data["funnel_elements"]) > 0:
                current_context += "Элементы продуктовой воронки:\n"
                for i, element in enumerate(current_data["funnel_elements"], 1):
                    current_context += f"  {i}. {element.get('name')}: {element.get('description')}\n"
            else:
                current_context += "Элементы продуктовой воронки: Не заполнены\n"
        
        # Формируем контекст из истории чата, если она предоставлена
        chat_context = ""
        if chat_history and len(chat_history) > 0:
            chat_context = "\nИстория диалога (последние сообщения):\n\n"
            # Берем только последние 5-8 сообщений для контекста, чтобы не превышать лимиты
            recent_messages = chat_history[-8:] if len(chat_history) > 8 else chat_history
            for msg in recent_messages:
                role = "Пользователь" if msg["role"] == "user" else "Ассистент"
                chat_context += f"{role}: {msg['content']}\n\n"
        
        prompt = f"""
        Ты выступаешь в роли ассистента по сбору информации об эксперте, его продукте/услуге и воронке продаж.
        
        {current_context}
        
        {chat_context}
        
        Новое сообщение пользователя:
        {text}
        
        Учитывая всю предыдущую историю диалога, текущие данные брифинга и новую информацию, извлеки и структурируй следующие данные:
        
        1. Уникальное торговое предложение (УТП) - что делает эксперта уникальным и какую пользу это приносит клиентам.
           УТП должно быть конкретным, привлекательным и отличающим эксперта от конкурентов.
        
        2. Описание продукта/услуги - подробно опиши, что предлагает эксперт, какие проблемы решает его продукт/услуга
           и какие конкретные выгоды получают клиенты. Включи ключевые характеристики и преимущества.
        
        3. Элементы продуктовой воронки - последовательные шаги или этапы, через которые проходит клиент от первого
           контакта с экспертом до совершения покупки и дальнейшего взаимодействия. Для каждого этапа укажи его название
           и подробное описание.
        
        Важно:
        - Если в новом сообщении нет информации по какому-то полю, но оно уже заполнено в текущих данных - сохрани существующее значение.
        - Если новая информация противоречит или дополняет существующую - интегрируй их вместе, сохраняя наиболее важные детали из обоих источников.
        - Если новое сообщение содержит не всю информацию - заполни только те поля, для которых есть данные.
        
        Верни результат ТОЛЬКО в формате JSON с полями:
        - utp: строка с УТП
        - product_description: строка с описанием продукта
        - funnel_elements: массив объектов с полями name (название этапа) и description (описание этапа)
        
        Не добавляй никаких пояснений до или после JSON.
        """
        
        # Настройка параметров генерации для более стабильного JSON
        generation_config = {
            "temperature": 0.2,  # Низкая температура для более предсказуемых ответов
            "max_output_tokens": 2048,  # Ограничение длины ответа
        }
        
        response = model.generate_content(prompt, generation_config=generation_config)
        result = response.text
        
        # Обработка ответа и преобразование в структурированный формат
        # Попытка найти JSON в ответе с помощью регулярного выражения
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            json_str = json_match.group(0)
            try:
                parsed_result = json.loads(json_str)
                
                # Объединение с текущими данными (если они есть)
                if current_data:
                    # Для УТП: если не заполнено в новом результате, но есть в текущих данных
                    if not parsed_result.get("utp") and current_data.get("utp"):
                        parsed_result["utp"] = current_data["utp"]
                    
                    # Для описания продукта: аналогично
                    if not parsed_result.get("product_description") and current_data.get("product_description"):
                        parsed_result["product_description"] = current_data["product_description"]
                    
                    # Для элементов воронки: объединяем списки, избегая дубликатов
                    if parsed_result.get("funnel_elements") and current_data.get("funnel_elements"):
                        # Создаем словарь существующих элементов по имени для быстрого поиска
                        existing_elements = {elem.get("name", ""): elem for elem in current_data["funnel_elements"]}
                        
                        for new_elem in parsed_result["funnel_elements"]:
                            if new_elem.get("name") in existing_elements:
                                # Если элемент уже существует, объединяем описания, если новое не пустое
                                if new_elem.get("description"):
                                    existing_elem = existing_elements[new_elem["name"]]
                                    if existing_elem.get("description") and new_elem.get("description") != existing_elem["description"]:
                                        # Объединяем описания, если они разные
                                        existing_elements[new_elem["name"]]["description"] = f"{existing_elem['description']} {new_elem['description']}"
                            else:
                                # Если это новый элемент, добавляем его
                                existing_elements[new_elem["name"]] = new_elem
                        
                        # Преобразуем обратно в список
                        parsed_result["funnel_elements"] = list(existing_elements.values())
                    elif not parsed_result.get("funnel_elements") and current_data.get("funnel_elements"):
                        parsed_result["funnel_elements"] = current_data["funnel_elements"]
                
                # Проверяем наличие всех необходимых полей
                if "utp" not in parsed_result:
                    parsed_result["utp"] = ""
                    
                if "product_description" not in parsed_result:
                    parsed_result["product_description"] = ""
                    
                if "funnel_elements" not in parsed_result or not isinstance(parsed_result["funnel_elements"], list):
                    parsed_result["funnel_elements"] = []
                    
                # Если список элементов воронки пуст, но есть хотя бы базовая информация, добавляем примерный элемент
                if len(parsed_result["funnel_elements"]) == 0 and (parsed_result["utp"] or parsed_result["product_description"]):
                    parsed_result["funnel_elements"].append({
                        "name": "Первичный контакт", 
                        "description": "Первое знакомство клиента с продуктом/услугой"
                    })
                    
            except json.JSONDecodeError:
                # Если не удалось распарсить JSON, используем запасной вариант
                logger.error(f"Не удалось распарсить JSON из ответа: {result}")
                
                # Если есть текущие данные, используем их как основу
                if current_data:
                    parsed_result = current_data.copy()
                    # Добавляем новую информацию из текста, если текущие данные неполные
                    if not parsed_result.get("utp"):
                        parsed_result["utp"] = text[:100] + "..." if len(text) > 100 else text
                else:
                    parsed_result = {
                        "utp": text[:100] + "..." if len(text) > 100 else text,
                        "product_description": "Требуется дополнительная информация",
                        "funnel_elements": [
                            {"name": "Первичный контакт", "description": "Первое знакомство клиента с продуктом/услугой"}
                        ]
                    }
        else:
            # Если JSON не найден, создаем базовую структуру или используем текущие данные
            logger.error(f"JSON не найден в ответе: {result}")
            
            if current_data:
                parsed_result = current_data.copy()
                # Если данные были, но не полные, пытаемся добавить новую информацию
                if not parsed_result.get("utp") or not parsed_result.get("product_description"):
                    if not parsed_result.get("utp"):
                        parsed_result["utp"] = text[:100] + "..." if len(text) > 100 else text
            else:
                parsed_result = {
                    "utp": text[:100] + "..." if len(text) > 100 else text,
                    "product_description": "Требуется дополнительная информация",
                    "funnel_elements": [
                        {"name": "Первичный контакт", "description": "Первое знакомство клиента с продуктом/услугой"}
                    ]
                }
        
        # Рассчитываем процент заполнения
        completion_percentage = calculate_completion_percentage(parsed_result)
        
        # Генерируем саммари этапа (для последующего использования)
        stage_summary = generate_stage_summary(parsed_result)
        
        return {
            "status": "success", 
            "data": parsed_result,
            "completion_percentage": completion_percentage,
            "stage_summary": stage_summary
        }
    except Exception as e:
        logger.error(f"Ошибка при анализе информации: {e}")
        return {"status": "error", "message": str(e)}

def calculate_completion_percentage(briefing_data: Dict[str, Any]) -> int:
    """
    Рассчитывает процент заполнения брифинга
    """
    total_fields = 3  # УТП, описание продукта, элементы воронки
    filled_fields = 0
    
    # Проверка заполнения УТП
    if briefing_data.get("utp") and len(briefing_data["utp"].strip()) > 10:
        filled_fields += 1
    
    # Проверка заполнения описания продукта
    if briefing_data.get("product_description") and len(briefing_data["product_description"].strip()) > 20:
        filled_fields += 1
    
    # Проверка заполнения элементов воронки
    if briefing_data.get("funnel_elements") and len(briefing_data["funnel_elements"]) > 0:
        # Проверяем качество заполнения элементов воронки
        valid_elements = 0
        for element in briefing_data["funnel_elements"]:
            if element.get("name") and element.get("description") and len(element["description"]) > 10:
                valid_elements += 1
        
        # Если есть хотя бы один качественный элемент, считаем поле заполненным
        if valid_elements > 0:
            filled_fields += 1
    
    # Вычисляем процент заполнения
    return int((filled_fields / total_fields) * 100)

def generate_stage_summary(briefing_data: Dict[str, Any]) -> str:
    """
    Генерирует саммари текущего этапа (брифинг эксперта)
    """
    summary = "Саммари этапа 'Брифинг эксперта':\n\n"
    
    # Добавляем УТП
    if briefing_data.get("utp"):
        summary += f"УТП: {briefing_data['utp']}\n\n"
    else:
        summary += "УТП: Не определено\n\n"
    
    # Добавляем описание продукта
    if briefing_data.get("product_description"):
        summary += f"Описание продукта/услуги: {briefing_data['product_description']}\n\n"
    else:
        summary += "Описание продукта/услуги: Не определено\n\n"
    
    # Добавляем элементы воронки
    summary += "Элементы продуктовой воронки:\n"
    if briefing_data.get("funnel_elements") and len(briefing_data["funnel_elements"]) > 0:
        for i, element in enumerate(briefing_data["funnel_elements"], 1):
            summary += f"{i}. {element.get('name', 'Этап')} - {element.get('description', 'Нет описания')}\n"
    else:
        summary += "Элементы воронки не определены\n"
    
    return summary


def generate_project_summary(project_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Генерирует саммари проекта на основе его данных
    
    Args:
        project_data: Данные проекта, включая briefing_data и другие поля
    
    Returns:
        Dict: Результат с саммари проекта
    """
    try:
        # Получаем модель по умолчанию
        model = get_gemini_model()
        if not model:
             logger.error("Не удалось получить модель Gemini для generate_project_summary.")
             return {"status": "error", "message": "Модель Gemini недоступна"}

        # Формируем контекст из данных проекта
        project_context = "Данные проекта:\n"
        
        # Добавляем название и описание проекта
        project_context += f"Название: {project_data.get('name', 'Без названия')}\n"
        if project_data.get('description'):
            project_context += f"Описание: {project_data['description']}\n"
        
        # Добавляем данные брифинга, если они есть
        briefing_data = project_data.get('briefing_data', {})
        if briefing_data:
            project_context += "\nДанные брифинга:\n"
            
            if briefing_data.get("utp"):
                project_context += f"УТП: {briefing_data['utp']}\n"
            
            if briefing_data.get("product_description"):
                project_context += f"Описание продукта: {briefing_data['product_description']}\n"
            
            if briefing_data.get("funnel_elements") and len(briefing_data["funnel_elements"]) > 0:
                project_context += "Элементы продуктовой воронки:\n"
                for i, element in enumerate(briefing_data["funnel_elements"], 1):
                    project_context += f"  {i}. {element.get('name')}: {element.get('description', 'Нет описания')}\n"
        
        prompt = f"""
        Ты - ассистент, который помогает создать краткое и информативное описание проекта.
        
        {project_context}
        
        На основе предоставленных данных, создай краткое саммари проекта, которое:
        1. Описывает основную суть проекта в 2-3 предложениях
        2. Выделяет ключевые особенности и преимущества
        3. Кратко описывает целевую аудиторию и ценность для неё
        4. Имеет профессиональный, но дружелюбный тон
        
        Саммари должно быть лаконичным (не более 300 слов) и хорошо структурированным.
        """
        
        generation_config = {
            "temperature": 0.3,  # Низкая температура для более предсказуемых ответов
            "max_output_tokens": 1024,  # Ограничение длины ответа
        }
        
        response = model.generate_content(prompt, generation_config=generation_config)
        summary = response.text.strip()
        
        return {
            "status": "success", 
            "summary": summary
        }
    except Exception as e:
        logger.error(f"Ошибка при генерации саммари проекта: {e}")
        return {"status": "error", "message": str(e)}

# Генерация уточняющих вопросов
def generate_follow_up_questions(briefing_data: Dict[str, Any], chat_history: List[Dict[str, str]] = None) -> List[str]:
    """
    Генерирует уточняющие вопросы на основе текущих данных брифинга и истории диалога
    
    Args:
        briefing_data: Текущие данные брифинга
        chat_history: История диалога
    
    Returns:
        List[str]: Список уточняющих вопросов
    """
    try:
        # Получаем модель по умолчанию
        model = get_gemini_model()
        if not model:
             logger.error("Не удалось получить модель Gemini для generate_follow_up_questions.")
             # Возвращаем стандартные вопросы в случае ошибки
             return ["Расскажите подробнее о вашем продукте или услуге?",
                     "Что делает ваше предложение уникальным на рынке?"]

        # Определяем, какие поля заполнены недостаточно
        missing_info = []
        
        # Проверка УТП
        if not briefing_data.get("utp") or len(briefing_data["utp"].strip()) < 15:
            missing_info.append("УТП (Уникальное Торговое Предложение)")
        
        # Проверка описания продукта
        if not briefing_data.get("product_description") or len(briefing_data["product_description"].strip()) < 30:
            missing_info.append("описание продукта/услуги")
        
        # Проверка элементов воронки
        if not briefing_data.get("funnel_elements") or len(briefing_data["funnel_elements"]) < 2:
            missing_info.append("элементы продуктовой воронки (нужно минимум 2-3 этапа)")
        else:
            # Проверка качества заполнения элементов воронки
            for element in briefing_data["funnel_elements"]:
                if not element.get("description") or len(element["description"]) < 15:
                    missing_info.append(f"подробное описание этапа '{element.get('name', 'Неизвестный этап')}'")
        
        # Если все заполнено достаточно хорошо, возвращаем пустой список
        if not missing_info:
            return ["У вас уже заполнены все необходимые поля! Вы можете перейти к следующему этапу или дополнить существующую информацию."]
        
        # Формируем контекст из истории чата, если она предоставлена
        chat_context = ""
        already_asked_questions = []
        
        if chat_history and len(chat_history) > 0:
            # Собираем последние вопросы ассистента, чтобы не повторяться
            for msg in chat_history:
                if msg["role"] == "assistant" and "?" in msg["content"]:
                    # Извлекаем вопросы из сообщения ассистента
                    questions = [q.strip() for q in re.findall(r'[^.!?]*\?', msg["content"])]
                    already_asked_questions.extend(questions)
            
            # Добавляем контекст из последних нескольких сообщений
            recent_messages = chat_history[-5:] if len(chat_history) > 5 else chat_history
            chat_context = "История диалога (последние сообщения):\n\n"
            for msg in recent_messages:
                role = "Пользователь" if msg["role"] == "user" else "Ассистент"
                chat_context += f"{role}: {msg['content']}\n\n"
        
        # Формируем текущий контекст брифинга
        briefing_context = "Текущие данные брифинга:\n"
        
        if briefing_data.get("utp"):
            briefing_context += f"УТП: {briefing_data['utp']}\n\n"
        else:
            briefing_context += "УТП: Не заполнено\n\n"
        
        if briefing_data.get("product_description"):
            briefing_context += f"Описание продукта: {briefing_data['product_description']}\n\n"
        else:
            briefing_context += "Описание продукта: Не заполнено\n\n"
        
        if briefing_data.get("funnel_elements") and len(briefing_data["funnel_elements"]) > 0:
            briefing_context += "Элементы продуктовой воронки:\n"
            for i, element in enumerate(briefing_data["funnel_elements"], 1):
                briefing_context += f"  {i}. {element.get('name')}: {element.get('description', 'Нет описания')}\n"
        else:
            briefing_context += "Элементы продуктовой воронки: Не заполнены\n"
        
        # Список уже заданных вопросов
        asked_questions_context = ""
        if already_asked_questions:
            asked_questions_context = "Вопросы, которые уже были заданы (не повторять их):\n"
            for i, q in enumerate(already_asked_questions[-10:], 1):  # Берем только последние 10 вопросов
                asked_questions_context += f"{i}. {q}\n"
        
        prompt = f"""
        Ты - ассистент, который помогает заполнить брифинг эксперта.
        
        {briefing_context}
        
        {chat_context}
        
        {asked_questions_context}
        
        Необходимо дополнить информацию о: {', '.join(missing_info)}.
        
        Сгенерируй 2-3 уточняющих вопроса, которые помогут получить недостающую информацию.
        
        Требования к вопросам:
        1. Вопросы должны быть конкретными и направленными на получение именно той информации, которой не хватает
        2. Не повторяй вопросы, которые уже были заданы ранее
        3. Задавай открытые вопросы, которые требуют развернутого ответа
        4. Учитывай контекст диалога и уже известную информацию
        5. Формулируй вопросы дружелюбно и профессионально
        6. Первый вопрос должен быть самым важным
        
        Верни ТОЛЬКО список вопросов, без пояснений и вводных фраз. Каждый вопрос с новой строки.
        """
        
        generation_config = {
            "temperature": 0.7,  # Немного повышаем температуру для разнообразия вопросов
            "max_output_tokens": 1024,
        }
        
        response = model.generate_content(prompt, generation_config=generation_config)
        
        # Обрабатываем ответ
        questions_text = response.text.strip()
        
        # Разбиваем текст на отдельные вопросы
        questions = [q.strip() for q in questions_text.split('\n') if q.strip() and '?' in q]
        
        # Если вопросов нет или парсинг не удался, возвращаем базовые вопросы
        if not questions:
            basic_questions = []
            if "УТП" in ''.join(missing_info):
                basic_questions.append("Что делает ваш продукт или услугу уникальными на рынке? Какую конкретную пользу это приносит клиентам?")
            
            if "описание продукта" in ''.join(missing_info):
                basic_questions.append("Расскажите подробнее о вашем продукте или услуге: какие основные функции или особенности он имеет? Какие проблемы клиентов он решает?")
            
            if "воронки" in ''.join(missing_info):
                basic_questions.append("Опишите, пожалуйста, как клиент взаимодействует с вашим продуктом от первого знакомства до покупки? Какие этапы проходит клиент?")
            
            if not basic_questions:
                basic_questions.append("Не могли бы вы рассказать больше о вашем бизнесе, чтобы мы могли лучше понять, как помочь вам?")
            
            return basic_questions
        
        # Ограничиваем количество вопросов до 3, чтобы не перегружать пользователя
        return questions[:3]
    
    except Exception as e:
        logger.error(f"Ошибка при генерации уточняющих вопросов: {e}")
        return ["Расскажите подробнее о вашем продукте или услуге?", 
                "Что делает ваше предложение уникальным на рынке?"]

def analyze_document_content(text: str, current_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Анализирует содержимое загруженного документа для извлечения информации о продукте/услуге
    
    Args:
        text: Текстовое содержимое документа
        current_data: Текущие данные брифинга (если есть)
    
    Returns:
        Dict: Результат анализа с обновленными данными
    """
    try:
        # Получаем модель по умолчанию
        model = get_gemini_model()
        if not model:
             logger.error("Не удалось получить модель Gemini для analyze_document_content.")
             return {"status": "error", "message": "Модель Gemini недоступна"}

        # Если текст слишком длинный, ограничиваем его размер (модели имеют лимиты)
        if len(text) > 30000:
            # Берем начало и конец документа, где обычно содержится самая важная информация
            truncated_text = text[:15000] + "\n[...]
" + text[-15000:]
        else:
            truncated_text = text
        
        # Формируем контекст из текущих данных, если они есть
        current_context = ""
        if current_data:
            current_context = "\nТекущие данные брифинга:\n"
            
            if current_data.get("utp"):
                current_context += f"УТП: {current_data['utp']}\n"
            else:
                current_context += "УТП: Не заполнено\n"
            
            if current_data.get("product_description"):
                current_context += f"Описание продукта: {current_data['product_description']}\n"
            else:
                current_context += "Описание продукта: Не заполнено\n"
            
            if current_data.get("funnel_elements") and len(current_data["funnel_elements"]) > 0:
                current_context += "Элементы продуктовой воронки:\n"
                for i, element in enumerate(current_data["funnel_elements"], 1):
                    current_context += f"  {i}. {element.get('name')}: {element.get('description')}\n"
            else:
                current_context += "Элементы продуктовой воронки: Не заполнены\n"
        
        prompt = f"""
        Ты выступаешь в роли ассистента по анализу документов и извлечению информации для брифинга.
        
        {current_context}
        
        Из предоставленного документа нужно извлечь и структурировать следующие данные:
        
        1. Уникальное торговое предложение (УТП) - что делает продукт/услугу уникальными и какую пользу они приносят клиентам.
           УТП должно быть конкретным, привлекательным и отличающим от конкурентов.
        
        2. Описание продукта/услуги - подробно опиши, что предлагается, какие проблемы решает продукт/услуга
           и какие конкретные выгоды получают клиенты. Включи ключевые характеристики и преимущества.
        
        3. Элементы продуктовой воронки - последовательные шаги или этапы, через которые проходит клиент от первого
           контакта до совершения покупки и дальнейшего взаимодействия. Для каждого этапа укажи его название
           и подробное описание.
        
        Важно:
        - Если в документе нет информации по какому-то полю, но оно уже заполнено в текущих данных - сохрани существующее значение.
        - Если информация в документе дополняет существующую - объедини их, сохраняя наиболее важные детали.
        - Если не удается найти какую-то информацию в документе - используй то, что уже есть, или оставь поле пустым.
        
        Содержимое документа для анализа:
        {truncated_text}
        
        Верни результат ТОЛЬКО в формате JSON с полями:
        - utp: строка с УТП
        - product_description: строка с описанием продукта
        - funnel_elements: массив объектов с полями name (название этапа) и description (описание этапа)
        
        Не добавляй никаких пояснений до или после JSON.
        """
        
        # Настройка параметров генерации
        generation_config = {
            "temperature": 0.2,  # Низкая температура для более предсказуемых ответов
            "max_output_tokens": 2048,  # Ограничение длины ответа
        }
        
        response = model.generate_content(prompt, generation_config=generation_config)
        result = response.text
        
        # Обработка ответа и преобразование в структурированный формат
        # Попытка найти JSON в ответе с помощью регулярного выражения
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            json_str = json_match.group(0)
            try:
                parsed_result = json.loads(json_str)
                
                # Объединение с текущими данными (если они есть)
                if current_data:
                    # Для УТП: если не заполнено в новом результате, но есть в текущих данных
                    if not parsed_result.get("utp") and current_data.get("utp"):
                        parsed_result["utp"] = current_data["utp"]
                    
                    # Для описания продукта: аналогично
                    if not parsed_result.get("product_description") and current_data.get("product_description"):
                        parsed_result["product_description"] = current_data["product_description"]
                    
                    # Для элементов воронки: объединяем списки, избегая дубликатов
                    if parsed_result.get("funnel_elements") and current_data.get("funnel_elements"):
                        # Создаем словарь существующих элементов по имени для быстрого поиска
                        existing_elements = {elem.get("name", ""): elem for elem in current_data["funnel_elements"]}
                        
                        for new_elem in parsed_result["funnel_elements"]:
                            if new_elem.get("name") in existing_elements:
                                # Если элемент уже существует, объединяем описания, если новое не пустое
                                if new_elem.get("description"):
                                    existing_elem = existing_elements[new_elem["name"]]
                                    if existing_elem.get("description") and new_elem.get("description") != existing_elem["description"]:
                                        # Объединяем описания, если они разные
                                        existing_elements[new_elem["name"]]["description"] = f"{existing_elem['description']} {new_elem['description']}"
                            else:
                                # Если это новый элемент, добавляем его
                                existing_elements[new_elem["name"]] = new_elem
                        
                        # Преобразуем обратно в список
                        parsed_result["funnel_elements"] = list(existing_elements.values())
                    elif not parsed_result.get("funnel_elements") and current_data.get("funnel_elements"):
                        parsed_result["funnel_elements"] = current_data["funnel_elements"]
                
                # Проверяем наличие всех необходимых полей
                if "utp" not in parsed_result:
                    parsed_result["utp"] = ""
                    
                if "product_description" not in parsed_result:
                    parsed_result["product_description"] = ""
                    
                if "funnel_elements" not in parsed_result or not isinstance(parsed_result["funnel_elements"], list):
                    parsed_result["funnel_elements"] = []
                
            except json.JSONDecodeError:
                # Если не удалось распарсить JSON, используем запасной вариант
                logger.error(f"Не удалось распарсить JSON из ответа: {result}")
                
                # Если есть текущие данные, используем их как основу
                if current_data:
                    parsed_result = current_data.copy()
                    # Если у нас есть текущие данные, но не удалось распарсить новые,
                    # просто возвращаем текущие данные, чтобы не потерять их
                else:
                    # Создаем пустую структуру, которая будет дальше обрабатываться
                    parsed_result = {
                        "utp": "",
                        "product_description": "Не удалось извлечь информацию из документа",
                        "funnel_elements": []
                    }
        else:
            # Если JSON не найден, создаем базовую структуру или используем текущие данные
            logger.error(f"JSON не найден в ответе: {result}")
            
            if current_data:
                parsed_result = current_data.copy()
            else:
                parsed_result = {
                    "utp": "",
                    "product_description": "Не удалось извлечь информацию из документа",
                    "funnel_elements": []
                }
        
        # Рассчитываем процент заполнения
        completion_percentage = calculate_completion_percentage(parsed_result)
        
        # Генерируем саммари этапа (для последующего использования)
        stage_summary = generate_stage_summary(parsed_result)
        
        return {
            "status": "success", 
            "data": parsed_result,
            "completion_percentage": completion_percentage,
            "stage_summary": stage_summary
        }
    except Exception as e:
        logger.error(f"Ошибка при анализе документа: {e}")
        return {"status": "error", "message": str(e)}
