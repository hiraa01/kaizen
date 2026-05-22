from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
import json

from database import get_db
from models import Student
from core.logging_config import api_logger
from services.ai_service import get_ai_service

router = APIRouter()


class ChatMessageRequest(BaseModel):
    """Chatbot mesaj isteği"""
    student_id: int
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_history: Optional[List[dict]] = None  # Geçmiş konuşmalar


class ChatMessageResponse(BaseModel):
    """Chatbot mesaj yanıtı"""
    success: bool
    reply: str
    model: str = "gemini-1.5"
    error: Optional[str] = None


@router.post("/message", response_model=ChatMessageResponse)
async def send_chat_message(
    request: ChatMessageRequest,
    db: Session = Depends(get_db)
):
    """
    ✅ Gemini 1.5 Tabanlı Akıllı Chatbot
    Öğrencinin profiline uyarlanmış cevaplar sağlıyor
    """
    try:
        # Öğrenciyi al
        student = db.query(Student).filter(Student.id == request.student_id).first()
        
        if not student:
            api_logger.warning(
                f"Student not found for chat",
                student_id=request.student_id
            )
            return ChatMessageResponse(
                success=False,
                reply="Öğrenci bulunamadı. Lütfen profil tamamlamayı deneyin.",
                error="Student not found"
            )
        
        # Öğrenci bağlamını oluştur (RAG)
        student_context = {
            'id': student.id,
            'name': student.name,
            'field_type': student.field_type,
            'tyt_score': student.tyt_total_score,
            'ayt_score': student.ayt_total_score,
            'total_score': student.total_score,
            'target_university': student.target_university,
            'target_department': getattr(student, 'target_department', None),
            'preferred_cities': [],
            'interest_areas': []
        }
        
        # JSON field'leri parse et
        try:
            if student.preferred_cities:
                student_context['preferred_cities'] = json.loads(student.preferred_cities) if isinstance(student.preferred_cities, str) else student.preferred_cities
            if student.interest_areas:
                student_context['interest_areas'] = json.loads(student.interest_areas) if isinstance(student.interest_areas, str) else student.interest_areas
        except (json.JSONDecodeError, TypeError):
            api_logger.debug(f"Could not parse student preferences for student {student.id}")
        
        # AI Service'i al
        ai_service = get_ai_service()
        
        api_logger.info(
            f"Processing chat message with Gemini AI",
            student_id=request.student_id,
            message_length=len(request.message)
        )
        
        # Gemini'ye sor
        result = ai_service.chat(
            message=request.message,
            student_id=request.student_id,
            student_context=student_context,
            conversation_history=request.conversation_history
        )
        
        return ChatMessageResponse(
            success=result.get('success', False),
            reply=result.get('response', ''),
            model=result.get('model', 'gemini-1.5'),
            error=result.get('error', None)
        )
        
    except Exception as e:
        api_logger.error(
            f"Error processing chat message: {str(e)}",
            error=str(e),
            student_id=request.student_id,
            error_type=type(e).__name__
        )
        return ChatMessageResponse(
            success=False,
            reply=f"Mesaj işlenemedi. Lütfen daha sonra tekrar deneyin.",
            error=str(e)
        )