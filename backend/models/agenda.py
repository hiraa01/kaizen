from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class AgendaItem(Base):
    """Ajanda öğeleri (görevler, hatırlatıcılar)"""
    __tablename__ = "agenda_items"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    is_completed = Column(Boolean, default=False, index=True)
    priority = Column(String(20), default="medium")  # low, medium, high
    category = Column(String(50), nullable=True)  # Ders, Sınav, Ödev, vb.

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    student = relationship("Student", back_populates="agenda_items")

    __table_args__ = (
        Index('ix_agenda_items_student_due_date', 'student_id', 'due_date'),
    )

    def __repr__(self):
        return f"<AgendaItem(id={self.id}, title='{self.title[:30]}...', student_id={self.student_id})>"
