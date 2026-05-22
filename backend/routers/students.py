from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import json

from database import get_db
from models import Student, User
from schemas.student import (
    StudentCreate,
    StudentUpdate,
    StudentResponse,
    StudentListResponse,
    StudentMlScheduleUpdate,
    StudentMlScheduleResponse,
)
from schemas.university import DepartmentWithUniversityResponse
from services.score_calculator import ScoreCalculator
from core.logging_config import api_logger
from services.recommendation_engine import RecommendationEngine
from routers.ml_recommendations import train_models_background
from core.exceptions import StudentNotFoundError, InvalidScoreError
from core.auth_dependencies import get_current_user_from_token
from services.ml_schedule_utils import compute_days_until_next_ml_training

router = APIRouter()


@router.post("", response_model=StudentResponse)
async def create_student(
    student: StudentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
):
    """Yeni öğrenci profili oluştur"""
    try:
        api_logger.info(
            "Creating new student profile",
            user_id=current_user.id,
            name=student.name,
            email=student.email,
            phone=student.phone,
        )
        
        # ✅ IMPORTANT: Never trust any user_id from client payload.
        # Force user_id from the token-derived current_user.
        user_id: int = current_user.id
        
        # ✅ 1. Mükerrer kayıt kontrolü - Bu user_id'ye ait student var mı?
        existing_student = db.query(Student).filter(Student.user_id == user_id).first()
        if existing_student:
            api_logger.info("Student profile already exists, returning existing", 
                          student_id=existing_student.id, user_id=user_id)
            return existing_student
        
        # ✅ 2. Puanları hesapla
        student_data = student.dict()
        student_data["user_id"] = current_user.id  # ✅ Token'dan gelen ID'yi zorla
        # Email/phone may be omitted by client; use current user as fallback.
        if not student_data.get("email") and current_user.email:
            student_data["email"] = current_user.email
        if not student_data.get("phone") and current_user.phone:
            student_data["phone"] = current_user.phone
        scores = ScoreCalculator.calculate_all_scores(student_data)
        
        # ✅ 3. JSON alanları için dönüşüm
        preferred_cities = json.dumps(student.preferred_cities) if student.preferred_cities else None
        preferred_university_types = json.dumps(student.preferred_university_types) if student.preferred_university_types else None
        preferred_departments = json.dumps(student.preferred_departments) if student.preferred_departments else None
        interest_areas = json.dumps(student.interest_areas) if student.interest_areas else None
        
        # ✅ 4. Veritabanı nesnesi oluştur - user_id'yi zorla ata
        db_student = Student(
            user_id=user_id,  # ✅ Authentication'dan gelen user_id zorla atanıyor
            name=student.name,
            email=student_data.get("email"),
            phone=student_data.get("phone"),
            class_level=student.class_level,
            exam_type=student.exam_type,
            field_type=student.field_type,
            tyt_turkish_net=student.tyt_turkish_net,
            tyt_math_net=student.tyt_math_net,
            tyt_social_net=student.tyt_social_net,
            tyt_science_net=student.tyt_science_net,
            ayt_math_net=student.ayt_math_net,
            ayt_physics_net=student.ayt_physics_net,
            ayt_chemistry_net=student.ayt_chemistry_net,
            ayt_biology_net=student.ayt_biology_net,
            ayt_literature_net=student.ayt_literature_net,
            ayt_history1_net=student.ayt_history1_net,
            ayt_geography1_net=student.ayt_geography1_net,
            ayt_philosophy_net=student.ayt_philosophy_net,
            ayt_history2_net=student.ayt_history2_net,
            ayt_geography2_net=student.ayt_geography2_net,
            ayt_religion_net=student.ayt_religion_net,
            ayt_foreign_language_net=student.ayt_foreign_language_net,
            diploma_grade=student.diploma_grade,
            student_status=student.student_status or "student",
            preferred_cities=preferred_cities,
            preferred_university_types=preferred_university_types,
            preferred_departments=preferred_departments,
            budget_preference=student.budget_preference,
            scholarship_preference=student.scholarship_preference,
            interest_areas=interest_areas,
            ml_update_frequency=student.ml_update_frequency,
            **scores
        )
        
        db.add(db_student)
        db.commit()
        db.refresh(db_student)
        
        api_logger.info("Student profile created successfully", student_id=db_student.id, user_id=user_id)
        return db_student
        
    except HTTPException:
        # HTTPException'ları olduğu gibi yukarı fırlat
        raise
    except InvalidScoreError as e:
        api_logger.error(f"Invalid score error: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        api_logger.error(f"Error creating student: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Öğrenci profili oluşturulurken bir hata oluştu")


@router.get("", response_model=StudentListResponse)
async def get_students(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Öğrenci listesini getir"""
    students = db.query(Student).offset(skip).limit(limit).all()
    total = db.query(Student).count()
    
    return StudentListResponse(
        students=students,
        total=total,
        page=skip // limit + 1,
        size=limit
    )


@router.patch(
    "/{student_id}/ml-update-frequency",
    response_model=StudentMlScheduleResponse,
)
async def update_student_ml_update_frequency(
    student_id: int,
    body: StudentMlScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
):
    """Öğrencinin ML model yenileme sıklığını (gün) günceller."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if student is None or student.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    student.ml_update_frequency = body.ml_update_frequency
    db.commit()
    db.refresh(student)
    eta = compute_days_until_next_ml_training(
        student.ml_last_trained_at,
        student.ml_update_frequency,
    )
    return StudentMlScheduleResponse(
        ml_update_frequency=student.ml_update_frequency,
        ml_last_trained_at=student.ml_last_trained_at,
        days_until_next_ml_training=eta,
        message="ML güncelleme sıklığı kaydedildi.",
    )


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(student_id: int, db: Session = Depends(get_db)):
    """Belirli bir öğrenciyi getir"""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    return student


@router.put("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: int, 
    student_update: StudentUpdate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Öğrenci bilgilerini güncelle"""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    
    # Güncellenecek alanları belirle
    update_data = student_update.dict(exclude_unset=True)
    
    score_recalc_keys = {
        'tyt_turkish_net', 'tyt_math_net', 'tyt_social_net', 'tyt_science_net',
        'ayt_math_net', 'ayt_physics_net', 'ayt_chemistry_net', 'ayt_biology_net',
        'ayt_literature_net', 'ayt_history1_net', 'ayt_geography1_net', 'ayt_philosophy_net',
        'ayt_history2_net', 'ayt_geography2_net', 'ayt_religion_net', 'ayt_foreign_language_net',
        'diploma_grade', 'student_status', 'field_type', 'exam_type',
    }
    if any(key in update_data for key in score_recalc_keys):
        # Mevcut verilerle güncellenmiş verileri birleştir
        student_data = student.__dict__.copy()
        student_data.update(update_data)
        scores = ScoreCalculator.calculate_all_scores(student_data)
        update_data.update(scores)
    
    # JSON alanları için dönüşüm
    if 'preferred_cities' in update_data and update_data['preferred_cities']:
        update_data['preferred_cities'] = json.dumps(update_data['preferred_cities'])
    if 'preferred_university_types' in update_data and update_data['preferred_university_types']:
        update_data['preferred_university_types'] = json.dumps(update_data['preferred_university_types'])
    if 'preferred_departments' in update_data and update_data['preferred_departments']:
        update_data['preferred_departments'] = json.dumps(update_data['preferred_departments'])
    if 'interest_areas' in update_data and update_data['interest_areas']:
        update_data['interest_areas'] = json.dumps(update_data['interest_areas'])
    
    # ✅ field_type değişikliği kontrolü - Eğer alan türü değiştiyse, eski önerileri temizle
    old_field_type = student.field_type
    field_type_changed = 'field_type' in update_data and update_data['field_type'] != old_field_type
    
    # Güncellemeleri uygula
    for field, value in update_data.items():
        setattr(student, field, value)
    
    db.commit()
    db.refresh(student)
    
    # ✅ Eğer field_type değiştiyse, eski önerileri temizle (yeni alan türüne uygun öneriler oluşturulacak)
    if field_type_changed:
        from models import Recommendation
        deleted_count = db.query(Recommendation).filter(Recommendation.student_id == student_id).delete()
        db.commit()
        api_logger.info(
            f"Field type changed from {old_field_type} to {update_data['field_type']}, cleared {deleted_count} old recommendations",
            student_id=student_id,
            old_field_type=old_field_type,
            new_field_type=update_data['field_type']
        )

    # Tercihler değiştiğinde önerileri ve ML eğitimini arka planda tetikle
    try:
        def _regenerate_recommendations_task(student_id_inner: int):
            engine = RecommendationEngine(db)
            try:
                engine.generate_recommendations(student_id_inner, limit=50)
            except Exception as e:
                api_logger.error("Recommendation regen failed", user_id=student_id_inner, error=str(e))

        background_tasks.add_task(_regenerate_recommendations_task, student.id)
        background_tasks.add_task(train_models_background)
    except Exception as bt_err:
        api_logger.warning("Background tasks scheduling failed", error=str(bt_err))
    
    return student


@router.post("/{student_id}/add-preferred-department/{department_id}")
async def add_preferred_department(
    student_id: int,
    department_id: int,
    db: Session = Depends(get_db)
):
    """
    ✅ SWIPE MANTIĞI: Kullanıcı bir bölümü beğendiğinde (sağa kaydırdığında)
    bu bölümü tercih listesine ekler
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    
    # Bölüm var mı kontrol et
    from models import Department
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Bölüm bulunamadı")
    
    # Mevcut tercih listesini al
    import json
    preferred_departments = []
    if student.preferred_departments:
        try:
            preferred_departments = json.loads(student.preferred_departments) if isinstance(student.preferred_departments, str) else student.preferred_departments
        except:
            preferred_departments = []
    
    # Bölüm adını ekle (normalize edilmiş isim)
    dept_name = department.normalized_name or department.name
    if dept_name and dept_name not in preferred_departments:
        preferred_departments.append(dept_name)
        student.preferred_departments = json.dumps(preferred_departments)
        db.commit()
        db.refresh(student)
        
        api_logger.info("Preferred department added", student_id=student_id, department_id=department_id, department_name=dept_name)
        return {"message": "Bölüm tercih listesine eklendi", "department_name": dept_name}
    else:
        return {"message": "Bölüm zaten tercih listesinde", "department_name": dept_name}


@router.get("/{student_id}/targets", response_model=List[DepartmentWithUniversityResponse])
async def get_student_targets(
    student_id: int,
    db: Session = Depends(get_db)
):
    """
    ✅ HEDEFİM SAYFASI İÇİN: Öğrencinin hedef bölümlerini detaylı olarak döndürür
    
    Öğrencinin preferred_departments listesindeki bölüm isimlerine göre
    Department objelerini (University bilgileriyle birlikte) döndürür.
    """
    from models import Department, University
    from schemas.university import DepartmentWithUniversityResponse
    from sqlalchemy.orm import selectinload
    
    try:
        # Öğrenciyi bul
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
        
        # Öğrencinin tercih listesini al
        preferred_departments = []
        if student.preferred_departments:
            try:
                preferred_departments = json.loads(student.preferred_departments) if isinstance(student.preferred_departments, str) else student.preferred_departments
            except:
                preferred_departments = []
        
        if not preferred_departments:
            # Liste boşsa boş liste döndür
            return []
        
        # Bölüm isimlerine göre Department objelerini bul
        # normalized_name veya name'e göre eşleştir
        departments = []
        for dept_name in preferred_departments:
            if not dept_name:
                continue
            
            # Önce normalized_name'e göre ara, bulamazsan name'e göre ara
            dept = db.query(Department).options(selectinload(Department.university)).filter(
                (Department.normalized_name == dept_name) | (Department.name == dept_name)
            ).first()
            
            if dept:
                departments.append(dept)
        
        # DepartmentWithUniversityResponse formatına çevir
        result = []
        for dept in departments:
            # Attributes JSON string'den parse et
            attributes = []
            if dept.attributes:
                try:
                    if isinstance(dept.attributes, str):
                        attributes = json.loads(dept.attributes)
                    else:
                        attributes = dept.attributes
                except:
                    attributes = []
            
            # Requirements JSON string'den parse et
            requirements = None
            if dept.requirements:
                try:
                    if isinstance(dept.requirements, str):
                        requirements = json.loads(dept.requirements)
                    else:
                        requirements = dept.requirements
                except:
                    requirements = None
            
            # University bilgilerini hazırla
            university = dept.university
            university_response = {
                "id": university.id,
                "name": university.name,
                "city": university.city,
                "university_type": university.university_type,
                "website": university.website,
                "established_year": university.established_year,
                "latitude": university.latitude,
                "longitude": university.longitude,
                "logo_url": university.logo_url if hasattr(university, 'logo_url') else None,
                "created_at": university.created_at.isoformat() if university.created_at else None,
                "updated_at": university.updated_at.isoformat() if university.updated_at else None,
            }
            
            # Department bilgilerini hazırla
            dept_response = {
                "id": dept.id,
                "university_id": dept.university_id,
                "name": dept.name,
                "normalized_name": dept.normalized_name,
                "attributes": attributes,
                "field_type": dept.field_type,
                "language": dept.language,
                "faculty": dept.faculty,
                "duration": dept.duration,
                "degree_type": dept.degree_type,
                "min_score": dept.min_score,
                "min_rank": dept.min_rank,
                "quota": dept.quota,
                "scholarship_quota": dept.scholarship_quota,
                "tuition_fee": dept.tuition_fee,
                "has_scholarship": dept.has_scholarship,
                "last_year_min_score": dept.last_year_min_score,
                "last_year_min_rank": dept.last_year_min_rank,
                "last_year_quota": dept.last_year_quota,
                "description": dept.description,
                "requirements": requirements,
                "created_at": dept.created_at.isoformat() if dept.created_at else None,
                "updated_at": dept.updated_at.isoformat() if dept.updated_at else None,
                "university": university_response,
            }
            
            result.append(dept_response)
        
        api_logger.info("Student targets retrieved", student_id=student_id, count=len(result))
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Error getting student targets: {str(e)}", student_id=student_id, error=str(e))
        # Hata durumunda boş liste döndür (frontend'in çökmesini önle)
        return []


@router.delete("/{student_id}")
async def delete_student(student_id: int, db: Session = Depends(get_db)):
    """Öğrenciyi sil"""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    
    db.delete(student)
    db.commit()
    
    return {"message": "Öğrenci başarıyla silindi"}


@router.post("/{student_id}/calculate-scores")
async def calculate_scores(student_id: int, db: Session = Depends(get_db)):
    """Öğrencinin puanlarını yeniden hesapla"""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    
    student_data = student.__dict__.copy()
    scores = ScoreCalculator.calculate_all_scores(student_data)
    diploma_grade = student.diploma_grade
    student_status = student.student_status or "student"
    detailed = ScoreCalculator.calculate_all_scores_detailed(
        student_data,
        diploma_grade=diploma_grade,
        student_status=student_status,
    )

    for field, value in scores.items():
        setattr(student, field, value)

    db.commit()
    db.refresh(student)

    return {
        "message": "Puanlar başarıyla hesaplandı",
        "scores": scores,
        "detailed": detailed,
    }
