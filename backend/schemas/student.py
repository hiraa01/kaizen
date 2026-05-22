from pydantic import BaseModel, EmailStr, computed_field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import json


class StudentBase(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    class_level: str
    exam_type: str
    field_type: str
    
    # TYT Scores
    tyt_turkish_net: float = 0.0
    tyt_math_net: float = 0.0
    tyt_social_net: float = 0.0
    tyt_science_net: float = 0.0
    
    # AYT Scores
    ayt_math_net: float = 0.0
    ayt_physics_net: float = 0.0
    ayt_chemistry_net: float = 0.0
    ayt_biology_net: float = 0.0
    ayt_literature_net: float = 0.0
    ayt_history1_net: float = 0.0
    ayt_geography1_net: float = 0.0
    ayt_philosophy_net: float = 0.0
    ayt_history2_net: float = 0.0
    ayt_geography2_net: float = 0.0
    ayt_religion_net: float = 0.0  
    ayt_foreign_language_net: float = 0.0
    
    # Preferences
    preferred_cities: Optional[List[str]] = None
    preferred_university_types: Optional[List[str]] = None
    preferred_departments: Optional[List[str]] = None
    budget_preference: Optional[str] = None
    scholarship_preference: bool = False
    interest_areas: Optional[List[str]] = None
    
    # Profile Information
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    target_university: Optional[str] = None
    
    # ✅ OBP HESAPLAMA İÇİN YENİ ALANLAR
    diploma_grade: Optional[float] = None  # Mezun notası (0-100)
    student_status: str = 'student'  # 'student', 'graduated', 'placement_broken', 'no_obp'

    # ML retrain cadence (days)
    ml_update_frequency: int = 7

    @validator('ml_update_frequency')
    def validate_ml_update_frequency(cls, value: int) -> int:
        allowed = {3, 5, 7, 30}
        if value not in allowed:
            raise ValueError('ml_update_frequency must be one of 3, 5, 7, 30')
        return value

    @validator('student_status')
    def validate_student_status(cls, value: str) -> str:
        allowed = {'student', 'graduated', 'placement_broken', 'no_obp'}
        if value not in allowed:
            raise ValueError(f'student_status must be one of {sorted(allowed)}')
        return value

    @validator('diploma_grade')
    def validate_diploma_grade(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if value < 0 or value > 100:
            raise ValueError('diploma_grade must be between 0 and 100')
        return value

    @validator('field_type')
    def validate_field_type(cls, v):
        allowed_types = ['EA', 'SAY', 'SÖZ', 'DİL']
        if v not in allowed_types:
            raise ValueError(f'field_type must be one of {allowed_types}')
        return v

    @validator('exam_type')
    def validate_exam_type(cls, v):
        allowed_types = ['TYT', 'AYT', 'TYT+AYT']
        if v not in allowed_types:
            raise ValueError(f'exam_type must be one of {allowed_types}')
        return v


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    class_level: Optional[str] = None
    exam_type: Optional[str] = None
    field_type: Optional[str] = None
    
    # TYT Scores
    tyt_turkish_net: Optional[float] = None
    tyt_math_net: Optional[float] = None
    tyt_social_net: Optional[float] = None
    tyt_science_net: Optional[float] = None
    
    # AYT Scores
    ayt_math_net: Optional[float] = None
    ayt_physics_net: Optional[float] = None
    ayt_chemistry_net: Optional[float] = None
    ayt_biology_net: Optional[float] = None
    ayt_literature_net: Optional[float] = None
    ayt_history1_net: Optional[float] = None
    ayt_geography1_net: Optional[float] = None
    ayt_philosophy_net: Optional[float] = None
    ayt_history2_net: Optional[float] = None
    ayt_geography2_net: Optional[float] = None
    ayt_religion_net: Optional[float] = None  # Din Kültürü
    ayt_foreign_language_net: Optional[float] = None
    
    # Preferences
    preferred_cities: Optional[List[str]] = None
    preferred_university_types: Optional[List[str]] = None
    preferred_departments: Optional[List[str]] = None
    budget_preference: Optional[str] = None
    scholarship_preference: Optional[bool] = None
    interest_areas: Optional[List[str]] = None
    
    # Profile Information
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    target_university: Optional[str] = None
    
    # ✅ OBP HESAPLAMA İÇİN YENİ ALANLAR
    diploma_grade: Optional[float] = None  # Mezun notası (0-100)
    student_status: Optional[str] = None  # 'student', 'graduated', 'placement_broken', 'no_obp'

    ml_update_frequency: Optional[int] = None

    @validator('exam_type')
    def validate_exam_type_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        allowed_types = ['TYT', 'AYT', 'TYT+AYT']
        if value not in allowed_types:
            raise ValueError(f'exam_type must be one of {allowed_types}')
        return value

    @validator('field_type')
    def validate_field_type_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        allowed_types = ['EA', 'SAY', 'SÖZ', 'DİL']
        if value not in allowed_types:
            raise ValueError(f'field_type must be one of {allowed_types}')
        return value

    @validator('ml_update_frequency')
    def validate_ml_update_frequency_optional(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return value
        allowed = {3, 5, 7, 30}
        if value not in allowed:
            raise ValueError('ml_update_frequency must be one of 3, 5, 7, 30')
        return value

    @validator('student_status')
    def validate_student_status_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        allowed = {'student', 'graduated', 'placement_broken', 'no_obp'}
        if value not in allowed:
            raise ValueError(f'student_status must be one of {sorted(allowed)}')
        return value

    @validator('diploma_grade')
    def validate_diploma_grade_optional(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if value < 0 or value > 100:
            raise ValueError('diploma_grade must be between 0 and 100')
        return value


class StudentResponse(StudentBase):
    id: int
    tyt_total_score: float
    ayt_total_score: float
    total_score: float
    obp_score: Optional[float] = 0.0  # ✅ OBP eklendi
    rank: int
    percentile: float
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    target_university: Optional[str] = None
    ml_last_trained_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    @computed_field
    def days_until_next_ml_training(self) -> Optional[int]:
        from services.ml_schedule_utils import compute_days_until_next_ml_training

        return compute_days_until_next_ml_training(
            self.ml_last_trained_at,
            self.ml_update_frequency,
        )

    @validator('preferred_cities', 'preferred_university_types', 'preferred_departments', 'interest_areas', pre=True)
    def parse_json_fields(cls, v):
        """Database'den gelen JSON string'leri parse et"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v

    class Config:
        from_attributes = True


class StudentListResponse(BaseModel):
    students: List[StudentResponse]
    total: int
    page: int
    size: int


class StudentMlScheduleUpdate(BaseModel):
    ml_update_frequency: int

    @validator('ml_update_frequency')
    def validate_ml_schedule_frequency(cls, value: int) -> int:
        allowed = {3, 5, 7, 30}
        if value not in allowed:
            raise ValueError('ml_update_frequency must be one of 3, 5, 7, 30')
        return value


class StudentMlScheduleResponse(BaseModel):
    ml_update_frequency: int
    ml_last_trained_at: Optional[datetime] = None
    days_until_next_ml_training: Optional[int] = None
    message: str
