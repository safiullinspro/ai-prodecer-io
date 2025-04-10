from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import base64
import requests
from bs4 import BeautifulSoup

from app.db import get_sql_db
from app.db.models import Project, User, ChatMessage
from app.schemas.chat import ChatMessageCreate, ChatMessageResponse, ChatHistoryResponse
from app.services import auth, gemini

router = APIRouter()

@router.get("/{project_id}/messages", response_model=ChatHistoryResponse)
async def get_chat_history(project_id: int, db: Session = Depends(get_sql_db), current_user: User = Depends(auth.get_current_user)):
    """Получение истории сообщений чата для проекта"""
    # Проверяем, существует ли проект и принадлежит ли он текущему пользователю
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден"
        )
    
    # Получаем сообщения чата для проекта
    messages = db.query(ChatMessage).filter(ChatMessage.project_id == project_id).order_by(ChatMessage.created_at).all()
    
    return {"messages": messages}

@router.post("/{project_id}/messages", response_model=Dict[str, Any])
async def send_message(project_id: int, message: ChatMessageCreate, db: Session = Depends(get_sql_db), current_user: User = Depends(auth.get_current_user)):
    """Отправка сообщения в чат и получение ответа от Gemini"""
    # Проверяем, существует ли проект и принадлежит ли он текущему пользователю
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден"
        )
    
    # Сохраняем сообщение пользователя
    user_message = ChatMessage(
        project_id=project_id,
        role="user",
        content=message.content
    )
    
    db.add(user_message)
    db.commit()
    db.refresh(user_message)
    
    # Получаем историю сообщений для контекста
    chat_history = db.query(ChatMessage).filter(ChatMessage.project_id == project_id).order_by(ChatMessage.created_at).all()
    
    # Получаем ответ от Gemini с учетом контекста
    try:
        # Преобразуем историю чата в формат для Gemini
        chat_context = []
        for msg in chat_history:
            chat_context.append({"role": msg.role, "content": msg.content})
        
        # Получаем текущие данные брифинга из проекта
        current_briefing_data = project.briefing_data if project.briefing_data else {}
        
        # Анализируем сообщение и обновляем брифинг с учетом контекста чата и текущих данных
        analysis_result = gemini.analyze_expert_info(
            text=message.content, 
            chat_history=chat_context,
            current_data=current_briefing_data
        )
        
        if analysis_result["status"] == "success":
            # Обновляем данные брифинга в проекте
            briefing_data = analysis_result["data"]
            briefing_data["completion_percentage"] = analysis_result["completion_percentage"]
            
            # Сохраняем саммари этапа (может быть использовано позже для передачи в следующие этапы)
            if "stage_summary" in analysis_result:
                briefing_data["stage_summary"] = analysis_result["stage_summary"]
            
            # Обновляем проект с новыми данными брифинга
            project.briefing_data = briefing_data
            db.commit()
            
            # Определяем, нужны ли уточняющие вопросы
            if briefing_data["completion_percentage"] < 100:
                # Генерируем уточняющие вопросы с учетом контекста
                questions = gemini.generate_follow_up_questions(briefing_data, chat_context)
                
                # Формируем ответное сообщение с учетом процента заполнения
                if briefing_data["completion_percentage"] >= 85:
                    # Если форма почти заполнена, предлагаем завершить
                    assistant_content = f"Мы уже собрали значительную часть информации ({briefing_data['completion_percentage']}%). "
                    assistant_content += "Вы можете перейти к следующему этапу или дополнить информацию, ответив на эти вопросы:\n\n"
                else:
                    # Если форма заполнена менее чем на 85%, просим дополнить информацию
                    assistant_content = f"Я проанализировал информацию и обновил форму брифинга ({briefing_data['completion_percentage']}% заполнено). "
                    assistant_content += "Для более полного заполнения брифинга, пожалуйста, ответьте на следующие вопросы:\n\n"
                
                # Добавляем вопросы к сообщению
                assistant_content += "\n\n".join(questions)
                
                # Если заполнено менее 50%, предлагаем альтернативные способы предоставления информации
                if briefing_data["completion_percentage"] < 50:
                    assistant_content += "\n\nТакже вы можете загрузить КП/презентацию или указать ссылку на ваш сайт для более точного анализа."
            else:
                # Если форма заполнена полностью, сообщаем об этом
                assistant_content = "Отлично! Все необходимые данные собраны (100%). Вы можете перейти к следующему этапу."
                
                # Если хотим показать краткую сводку собранной информации
                assistant_content += "\n\nВот краткая сводка собранной информации:\n\n"
                
                if briefing_data.get("utp"):
                    assistant_content += f"✅ УТП: {briefing_data['utp']}\n\n"
                
                if briefing_data.get("product_description"):
                    # Ограничиваем длину для краткости
                    product_desc = briefing_data["product_description"]
                    if len(product_desc) > 150:
                        product_desc = product_desc[:150] + "..."
                    assistant_content += f"✅ Описание продукта: {product_desc}\n\n"
                
                assistant_content += "✅ Элементы воронки: "
                if briefing_data.get("funnel_elements") and len(briefing_data["funnel_elements"]) > 0:
                    funnel_elements = [elem.get("name", "Этап") for elem in briefing_data["funnel_elements"]]
                    assistant_content += ", ".join(funnel_elements)
                else:
                    assistant_content += "не определены"
        else:
            # Если анализ не удался, отправляем общий ответ
            assistant_content = "Я не смог проанализировать вашу информацию. Пожалуйста, предоставьте более подробные сведения о вашем продукте или услуге."
            assistant_content += "\n\nВы также можете загрузить КП/презентацию или указать ссылку на ваш сайт для более точного анализа."
    
    except Exception as e:
        # В случае ошибки отправляем сообщение об ошибке
        assistant_content = f"Произошла ошибка при обработке вашего сообщения. Пожалуйста, попробуйте еще раз или обратитесь в поддержку.\n\nТехническая информация: {str(e)}"
    
    # Сохраняем ответ ассистента
    assistant_message = ChatMessage(
        project_id=project_id,
        role="assistant",
        content=assistant_content
    )
    
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)
    
    # Возвращаем обновленный проект вместе с сообщением
    return {
        "status": "success",
        "message": {
            "id": assistant_message.id,
            "role": assistant_message.role,
            "content": assistant_message.content,
            "project": {
                "id": project.id,
                "briefing_data": project.briefing_data
            }
        }
    }

@router.post("/{project_id}/upload-file", response_model=Dict[str, Any])
async def upload_file(project_id: int, file_content: str = Body(..., embed=True), db: Session = Depends(get_sql_db), current_user: User = Depends(auth.get_current_user)):
    """Обработка загруженного файла"""
    # Проверяем, существует ли проект и принадлежит ли он текущему пользователю
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден"
        )
    
    # Извлекаем содержимое файла из base64
    try:
        # Предполагаем, что file_content приходит в формате data:application/pdf;base64,XXXXX...
        file_data = file_content.split(',')[1] if ',' in file_content else file_content
        
        # Декодируем base64 - теоретически может обрабатывать документы
        # Для простоты берем только первые 100000 символов
        decoded_content = base64.b64decode(file_data).decode('utf-8', errors='ignore')[:100000]
        
        # Сохраняем сообщение пользователя о загрузке файла
        user_message = ChatMessage(
            project_id=project_id,
            role="user",
            content=f"Загружен файл с содержимым типа {file_content.split(';')[0] if ';' in file_content else 'document'}"
        )
        
        db.add(user_message)
        db.commit()
        
        # Получаем текущие данные брифинга
        current_briefing_data = project.briefing_data if project.briefing_data else {}
        
        # Обрабатываем содержимое файла через Gemini API
        analysis_result = gemini.analyze_document_content(
            text=decoded_content,
            current_data=current_briefing_data
        )
        
        if analysis_result["status"] == "success":
            # Обновляем данные брифинга в проекте
            briefing_data = analysis_result["data"]
            briefing_data["completion_percentage"] = analysis_result["completion_percentage"]
            
            # Сохраняем саммари этапа
            if "stage_summary" in analysis_result:
                briefing_data["stage_summary"] = analysis_result["stage_summary"]
            
            # Обновляем проект с новыми данными брифинга
            project.briefing_data = briefing_data
            db.commit()
            
            # Формируем ответное сообщение
            if briefing_data["completion_percentage"] >= 80:
                assistant_content = f"Я проанализировал ваш файл и успешно извлек информацию для брифинга ({briefing_data['completion_percentage']}% заполнено).\n\n"
                assistant_content += "Вот что я узнал из вашего документа:\n\n"
                
                if briefing_data.get("utp"):
                    assistant_content += f"✅ УТП: {briefing_data['utp']}\n\n"
                
                if briefing_data.get("product_description"):
                    product_desc = briefing_data["product_description"]
                    if len(product_desc) > 150:
                        product_desc = product_desc[:150] + "..."
                    assistant_content += f"✅ Описание продукта: {product_desc}\n\n"
                
                if briefing_data.get("funnel_elements") and len(briefing_data["funnel_elements"]) > 0:
                    assistant_content += "✅ Найдены элементы продуктовой воронки\n\n"
                
                if briefing_data["completion_percentage"] < 100:
                    assistant_content += "Есть ли какая-то дополнительная информация, которую вы хотели бы добавить?"
            else:
                assistant_content = f"Я проанализировал ваш файл и извлек некоторую информацию ({briefing_data['completion_percentage']}% заполнено), но для полного заполнения брифинга нужны дополнительные данные.\n\n"
                
                # Генерируем вопросы для уточнения
                questions = gemini.generate_follow_up_questions(briefing_data, [])
                assistant_content += "Пожалуйста, ответьте на следующие вопросы:\n\n"
                assistant_content += "\n\n".join(questions)
        else:
            # Если анализ не удался
            assistant_content = "Я не смог полноценно проанализировать ваш файл. Возможно, формат документа не поддерживается или содержимое зашифровано.\n\n"
            assistant_content += "Пожалуйста, попробуйте предоставить информацию о вашем продукте или услуге в текстовом формате, ответив на следующие вопросы:\n\n"
            assistant_content += "1. Что представляет собой ваш продукт/услуга?\n"
            assistant_content += "2. В чем его уникальность по сравнению с конкурентами?\n"
            assistant_content += "3. Как происходит процесс продажи вашего продукта/услуги?"
    
    except Exception as e:
        # В случае ошибки при обработке файла
        assistant_content = f"Произошла ошибка при обработке вашего файла. Пожалуйста, проверьте формат документа и попробуйте еще раз или предоставьте информацию в текстовом виде.\n\nДеталь ошибки: {str(e)}"
        
        # Создаем минимальные данные брифинга если их нет
        if not project.briefing_data:
            project.briefing_data = {
                "utp": "",
                "product_description": "",
                "funnel_elements": [],
                "completion_percentage": 0
            }
            db.commit()
    
    # Сохраняем ответ ассистента
    assistant_message = ChatMessage(
        project_id=project_id,
        role="assistant",
        content=assistant_content
    )
    
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)
    
    # Возвращаем результат в правильном формате (как ожидает фронтенд)
    return {
        "status": "success",
        "message": {
            "id": assistant_message.id,
            "role": assistant_message.role,
            "content": assistant_message.content,
            "project": {
                "id": project.id,
                "briefing_data": project.briefing_data
            }
        }
    }

@router.post("/{project_id}/process-link", response_model=Dict[str, Any])
async def process_link(project_id: int, link: str = Body(..., embed=True), db: Session = Depends(get_sql_db), current_user: User = Depends(auth.get_current_user)):
    """Обработка ссылки на сайт"""
    # Проверяем, существует ли проект и принадлежит ли он текущему пользователю
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден"
        )
    
    # Сохраняем сообщение пользователя о ссылке
    user_message = ChatMessage(
        project_id=project_id,
        role="user",
        content=f"Ссылка на сайт: {link}"
    )
    
    db.add(user_message)
    db.commit()
    
    assistant_content = ""
    
    try:
        # Пытаемся получить содержимое по ссылке
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
            }
            response = requests.get(link, headers=headers, timeout=10)
            response.raise_for_status()  # Проверяем статус ответа
            
            # Получаем текст страницы и очищаем его
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Удаляем все скрипты, стили и другие ненужные элементы
            for script in soup(["script", "style", "meta", "noscript", "iframe"]):
                script.extract()
            
            # Извлекаем текст из HTML
            page_text = soup.get_text(separator="\n", strip=True)
            
            # Получаем текущие данные брифинга
            current_briefing_data = project.briefing_data if project.briefing_data else {}
            
            # Анализируем содержимое страницы через Gemini API
            analysis_result = gemini.analyze_document_content(
                text=page_text[:50000],  # Ограничиваем размер текста
                current_data=current_briefing_data
            )
            
            if analysis_result["status"] == "success":
                # Обновляем данные брифинга в проекте
                briefing_data = analysis_result["data"]
                briefing_data["completion_percentage"] = analysis_result["completion_percentage"]
                
                # Сохраняем саммари этапа
                if "stage_summary" in analysis_result:
                    briefing_data["stage_summary"] = analysis_result["stage_summary"]
                
                # Обновляем проект с новыми данными брифинга
                project.briefing_data = briefing_data
                db.commit()
                
                # Формируем ответное сообщение
                if briefing_data["completion_percentage"] >= 80:
                    assistant_content = f"Я проанализировал контент по вашей ссылке и успешно извлек информацию для брифинга ({briefing_data['completion_percentage']}% заполнено).\n\n"
                    assistant_content += "Вот что я узнал:\n\n"
                    
                    if briefing_data.get("utp"):
                        assistant_content += f"✅ УТП: {briefing_data['utp']}\n\n"
                    
                    if briefing_data.get("product_description"):
                        product_desc = briefing_data["product_description"]
                        if len(product_desc) > 150:
                            product_desc = product_desc[:150] + "..."
                        assistant_content += f"✅ Описание продукта: {product_desc}\n\n"
                    
                    if briefing_data.get("funnel_elements") and len(briefing_data["funnel_elements"]) > 0:
                        assistant_content += "✅ Найдены элементы продуктовой воронки\n\n"
                    
                    if briefing_data["completion_percentage"] < 100:
                        assistant_content += "Есть ли какая-то дополнительная информация, которую вы хотели бы добавить?"
                else:
                    assistant_content = f"Я проанализировал информацию по вашей ссылке и извлек некоторые данные ({briefing_data['completion_percentage']}% заполнено), но для полного заполнения брифинга нужны дополнительные детали.\n\n"
                    
                    # Генерируем вопросы для уточнения
                    questions = gemini.generate_follow_up_questions(briefing_data, [])
                    assistant_content += "Пожалуйста, ответьте на следующие вопросы:\n\n"
                    assistant_content += "\n\n".join(questions)
            else:
                # Если анализ не удался
                assistant_content = "Я не смог извлечь полезную информацию из страницы по вашей ссылке. Возможно, на странице недостаточно текстового контента или он защищен от автоматического извлечения.\n\n"
                assistant_content += "Пожалуйста, попробуйте предоставить информацию о вашем продукте или услуге в текстовом формате, ответив на следующие вопросы:\n\n"
                assistant_content += "1. Что представляет собой ваш продукт/услуга?\n"
                assistant_content += "2. В чем его уникальность по сравнению с конкурентами?\n"
                assistant_content += "3. Как происходит процесс продажи вашего продукта/услуги?"
        
        except requests.RequestException as req_error:
            # Если не удалось получить или обработать страницу
            logger.error(f"Ошибка при запросе веб-страницы: {req_error}")
            assistant_content = f"Не удалось получить содержимое по указанной ссылке. Возможно, сайт недоступен или имеет защиту от автоматического доступа.\n\nПожалуйста, попробуйте другую ссылку или предоставьте информацию о вашем продукте в текстовом виде."
        
        except Exception as web_error:
            # Если произошла другая ошибка при обработке страницы
            logger.error(f"Ошибка при обработке веб-страницы: {web_error}")
            assistant_content = f"Не удалось обработать содержимое по указанной ссылке. Возможно, формат страницы не подходит для автоматического анализа.\n\nПожалуйста, попробуйте другую ссылку или предоставьте информацию о вашем продукте в текстовом виде."
    
    except Exception as e:
        # В случае общей ошибки
        logger.error(f"Ошибка при обработке ссылки: {e}")
        assistant_content = f"Произошла ошибка при обработке вашей ссылки. Пожалуйста, проверьте ссылку и попробуйте еще раз или предоставьте информацию в текстовом виде.\n\nДеталь ошибки: {str(e)}"
        
        # Создаем минимальные данные брифинга если их нет
        if not project.briefing_data:
            project.briefing_data = {
                "utp": "",
                "product_description": "",
                "funnel_elements": [],
                "completion_percentage": 0
            }
            db.commit()
    
    # Сохраняем ответ ассистента
    assistant_message = ChatMessage(
        project_id=project_id,
        role="assistant",
        content=assistant_content
    )
    
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)
    
    # Возвращаем результат в правильном формате (как ожидает фронтенд)
    return {
        "status": "success",
        "message": {
            "id": assistant_message.id,
            "role": assistant_message.role,
            "content": assistant_message.content,
            "project": {
                "id": project.id,
                "briefing_data": project.briefing_data
            }
        }
    }