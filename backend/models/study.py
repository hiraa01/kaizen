from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class StudySession(Base):
    """Ders çalışma oturumları"""
    __tablename__ = "study_sessions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    subject = Column(String(100), nullable=False)  # Matematik, Fizik, vb.
    duration_minutes = Column(Integer, nullable=False, default=0)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    notes = Column(Text, nullable=True)
    efficiency_score = Column(Float, nullable=True)  # 0-100 arası verimlilik puanı

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    student = relationship("Student", back_populates="study_sessions")

    __table_args__ = (
        Index('ix_study_sessions_student_date', 'student_id', 'date'),
    )

    def __repr__(self):
        return f"<StudySession(id={self.id}, subject='{self.subject}', student_id={self.student_id}, duration={self.duration_minutes}min)>"
