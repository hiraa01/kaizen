from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class ChatMessage(Base):
    """Chatbot mesajları"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    message = Column(Text, nullable=False)
    reply = Column(Text, nullable=True)  # Bot'un cevabı
    intent = Column(String(50), nullable=True)  # Mesaj amacı (hesapla, öneri, vb.)
    is_from_bot = Column(Boolean, default=False)  # Bot'tan mı, kullanıcıdan mı

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("Student", back_populates="chat_messages")

    __table_args__ = (
        Index('ix_chat_messages_student_created', 'student_id', 'created_at'),
    )

    def __repr__(self):
        return f"<ChatMessage(id={self.id}, student_id={self.student_id}, is_from_bot={self.is_from_bot})>"
