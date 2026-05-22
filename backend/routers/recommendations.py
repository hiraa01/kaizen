# -*- coding: utf-8 -*-
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from models import Student, Recommendation, Department, Preference, University
from schemas.university import (
    RecommendationResponse,
    PreferenceCompatibilityRequest,
    PreferenceCompatibilityResponse,
    PreferenceCompatibilityBucket,
    RecommendationGenerateRequest,
)
from services.recommendation_engine import RecommendationEngine
from services.score_calculator import ScoreCalculator
from core.logging_config import api_logger

router = APIRouter()


def _student_has_target_labels(student: Student, db: Session) -> bool:
    """Return True if student has any active target department preference."""
    has_target_labels = False

    if student.preferred_departments:
        try:
            raw_pd = (
                json.loads(student.preferred_departments)
                if isinstance(student.preferred_departments, str)
                else student.preferred_departments
            )
            if isinstance(raw_pd, list):
                has_target_labels = any(
                    str(item).strip() for item in raw_pd if item is not None
                )
            elif isinstance(raw_pd, str):
                has_target_labels = bool(raw_pd.strip())
        except (json.JSONDecodeError, TypeError):
            # JSON parse edilemeyen ama dolu bir string de hedef olarak kabul edilir
            if isinstance(student.preferred_departments, str):
                has_target_labels = bool(student.preferred_departments.strip())

    target_department = getattr(student, "target_department", None)
    if target_department and str(target_department).strip():
        has_target_labels = True

    has_preference_targets = (
        db.query(Preference)
        .filter(Preference.student_id == student.id)
        .count()
        > 0
    )
    if has_preference_targets:
        has_target_labels = True

    return has_target_labels


@router.post("/generate/{student_id}", response_model=List[RecommendationResponse])
async def generate_recommendations(
    student_id: int,
    limit: int = Query(50, ge=1, le=200),
    w_c: float = Query(0.4, ge=0.0, le=1.0, description="Weight for compatibility"),
    w_s: float = Query(0.4, ge=0.0, le=1.0, description="Weight for success probability"),
    w_p: float = Query(0.2, ge=0.0, le=1.0, description="Weight for preference"),
    force_regenerate: bool = Query(False, description="Force regeneration even if recommendations exist"),
    payload: Optional[RecommendationGenerateRequest] = None,
    db: Session = Depends(get_db)
):
    """Öğrenci için tercih önerileri oluştur"""
    try:
        api_logger.info("Starting recommendation generation", user_id=student_id, limit=limit)
        
        # ✅ Öğrenci var mı kontrol et - get() yerine filter().first() kullan (modern SQLAlchemy)
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
        
        # ✅ KESİN FİLTRE: Öğrencinin field_type'ı yoksa hata ver
        if not student.field_type:
            raise HTTPException(status_code=400, detail="Öğrencinin alan türü (field_type) belirtilmemiş")
        
        # ✅ Cache kontrolü: Eğer öneriler varsa ve force_regenerate=False ise, mevcut önerileri döndür
        if not force_regenerate:
            existing_recs = db.query(Recommendation).filter(
                Recommendation.student_id == student_id
            ).order_by(Recommendation.final_score.desc()).limit(limit).all()
            
            if existing_recs and len(existing_recs) > 0:
                api_logger.info("Returning cached recommendations", user_id=student_id, count=len(existing_recs))
                # Mevcut önerileri formatla ve döndür
                from schemas.university import DepartmentWithUniversityResponse
                
                department_ids = {rec.department_id for rec in existing_recs}
                departments_dict = {
                    dept.id: dept
                    for dept in db.query(Department).filter(Department.id.in_(department_ids)).all()
                }
                university_ids = {dept.university_id for dept in departments_dict.values()}
                universities_dict = {
                    uni.id: uni
                    for uni in db.query(University).filter(University.id.in_(university_ids)).all()
                }
                
                result = []
                for rec in existing_recs:
                    department = departments_dict.get(rec.department_id)
                    if not department:
                        continue
                    
                    # ✅ KESİN FİLTRE (Hard Filter): Öğrencinin alanına uygun olmayan bölümleri filtrele
                    if student.field_type and department.field_type != student.field_type:
                        api_logger.debug(
                            f"Skipping cached recommendation {rec.id} - field_type mismatch: student={student.field_type}, department={department.field_type}",
                            recommendation_id=rec.id,
                            department_id=department.id
                        )
                        continue
                    
                    # ✅ NULL PUAN KORUMASI: Cache'den gelen önerilerde de kontrol et
                    if department.min_score is None or department.min_score <= 0:
                        api_logger.debug(
                            f"Skipping cached recommendation {rec.id} - department {department.id} has null min_score",
                            recommendation_id=rec.id,
                            department_id=department.id
                        )
                        continue
                    
                    university = universities_dict.get(department.university_id)
                    if not university:
                        continue
                    department_response = DepartmentWithUniversityResponse(
                        **department.__dict__,
                        university=university
                    )
                    result.append(RecommendationResponse(
                        **rec.__dict__,
                        department=department_response
                    ))
                
                # ✅ Eğer cache'den gelen sonuç varsa döndür
                if result:
                    return result
        
        # ✅ Önce eski önerileri temizle (yeniden hesaplama için)
        db.query(Recommendation).filter(Recommendation.student_id == student_id).delete()
        db.commit()
        
        # Öneri motorunu çalıştır (try-except ile güvenli hale getir)
        try:
            recommendation_engine = RecommendationEngine(db)
            # normalize weights (total>0 ise)
            total_w = max(1e-9, (w_c + w_s + w_p))
            weights = (w_c / total_w, w_s / total_w, w_p / total_w)
            preferred_university_ids: set[int] = set()

            # Frontend'den gelen sinyaller
            if payload is not None:
                preferred_university_ids.update(payload.saved_university_ids or [])
                preferred_university_ids.update(payload.liked_university_ids or [])
                preferred_university_ids.update(payload.preferred_university_ids or [])

            # Backend'de kayıtlı hedef bölümlerden üniversite sinyali üret
            preference_rows = (
                db.query(Department.university_id)
                .join(Preference, Preference.department_id == Department.id)
                .filter(Preference.student_id == student_id)
                .all()
            )
            preferred_university_ids.update(
                uni_id for (uni_id,) in preference_rows if uni_id is not None
            )

            recommendations = recommendation_engine.generate_recommendations(
                student_id,
                limit,
                weights,
                preferred_university_ids=preferred_university_ids,
            )
            
            # ✅ NULL PUAN KORUMASI: min_score None olan bölümleri filtrele
            filtered_recommendations = []
            for rec in recommendations:
                if hasattr(rec, 'department') and rec.department:
                    dept = rec.department
                    if hasattr(dept, 'min_score') and dept.min_score is not None and dept.min_score > 0:
                        filtered_recommendations.append(rec)
                    else:
                        api_logger.debug(
                            f"Skipping recommendation - department has null/zero min_score",
                            recommendation_id=getattr(rec, 'id', None),
                            department_id=getattr(dept, 'id', None) if hasattr(dept, 'id') else None
                        )
                else:
                    # Department bilgisi yoksa da ekle (fallback için)
                    filtered_recommendations.append(rec)
            
            recommendations = filtered_recommendations
            
        except Exception as engine_error:
            # ✅ Öneri motoru hatası durumunda logla ve fallback'e geç
            api_logger.error(
                f"Recommendation engine error: {str(engine_error)}",
                user_id=student_id,
                error=str(engine_error)
            )
            recommendations = []  # Boş liste - fallback'e geç
        
        # ✅ Eğer öneri bulunduysa döndür
        if recommendations and len(recommendations) > 0:
            api_logger.info("Recommendations generated successfully", user_id=student_id, count=len(recommendations))
            return recommendations

        # Hedef bölüm seçilmiş ama hiç eşleşme yoksa popüler listeyle doldurma (yanlış fakülte göstermeyi önle)
        has_target_labels = _student_has_target_labels(student, db)

        if has_target_labels:
            api_logger.info(
                "No recommendations after target-department filter; skipping popular fallback",
                user_id=student_id,
            )
            return []
        
        # ✅ FALLBACK: Eğer öneri bulunamazsa, en yüksek puanlı veya en çok kontenjanlı 20 bölümü "Popüler Bölümler" olarak döndür
        api_logger.info("No recommendations found, returning popular departments", user_id=student_id)
        from schemas.university import DepartmentWithUniversityResponse
        
        # ✅ min_score None olan bölümleri filtreleme dışında bırak
        popular_query = db.query(Department).filter(
            Department.min_score.isnot(None),
            Department.min_score > 0
        )
        
        # ✅ KESİN FİLTRE (Hard Filter): Öğrencinin alan türüne uygun popüler bölümleri getir
        # Özel Durum: Eğer öğrenci TYT (Önlisans) istiyorsa, sadece TYT bölümleri
        if student.exam_type and student.exam_type.upper() == 'TYT':
            popular_query = popular_query.filter(
                (Department.field_type == 'TYT') | 
                (Department.degree_type == 'Associate') |
                (Department.degree_type == 'Önlisans')
            )
        elif student.field_type:
            popular_query = popular_query.filter(Department.field_type == student.field_type)
        
        # Önce en yüksek puanlıları getir, sonra kontenjanı yüksek olanları
        popular_departments = popular_query.order_by(
            Department.min_score.desc(),
            Department.quota.desc().nullslast()
        ).limit(20).all()  # En yüksek puanlı 20 bölüm
        
        # Eğer alan türüne uygun yoksa, tüm popüler bölümleri getir
        if not popular_departments:
            popular_departments = db.query(Department).filter(
                Department.min_score.isnot(None),
                Department.min_score > 0
            ).order_by(
                Department.min_score.desc(),
                Department.quota.desc().nullslast()
            ).limit(20).all()
        
        # University'leri çek
        university_ids = {dept.university_id for dept in popular_departments}
        universities_dict = {
            uni.id: uni
            for uni in db.query(University).filter(University.id.in_(university_ids)).all()
        }
        
        # Response formatına çevir (Popüler Bölümler olarak)
        fallback_result = []
        for dept in popular_departments:
            university = universities_dict.get(dept.university_id)
            if not university:
                continue
            
            department_response = DepartmentWithUniversityResponse(
                **dept.__dict__,
                university=university
            )
            
            # Popüler fallback puanları: profile göre yaklaşık metrik hesapla
            student_score = (
                float(student.total_score)
                if student and student.total_score is not None
                else 200.0
            )
            score_gap = abs(float(dept.min_score or 0) - student_score)
            compatibility_score = round(max(25.0, min(90.0, 100.0 - score_gap * 1.2)), 1)
            success_probability = round(max(10.0, min(92.0, 85.0 - max(0.0, float((dept.min_score or 0) - student_score)) * 1.1)), 1)
            preference_score = round(max(35.0, compatibility_score - 8.0), 1)
            final_score = round(
                compatibility_score * 0.50
                + success_probability * 0.30
                + preference_score * 0.20,
                1,
            )

            fallback_result.append(RecommendationResponse(
                student_id=student_id,
                department_id=dept.id,
                department=department_response,
                compatibility_score=compatibility_score,
                success_probability=success_probability,
                preference_score=preference_score,
                final_score=final_score,
                recommendation_reason="Hedef dışı önerilen bölüm (genel popülerlik + puan yakınlığı)",
                is_safe_choice=final_score >= 75,
                is_dream_choice=final_score < 55,
                is_realistic_choice=55 <= final_score < 75
            ))
        
        api_logger.info("Returning popular departments as fallback", user_id=student_id, count=len(fallback_result))
        return fallback_result
        
    except HTTPException:
        # HTTPException'ları tekrar fırlat (404 gibi)
        raise
    except Exception as e:
        # ✅ FALLBACK: Herhangi bir hata durumunda popüler bölümleri döndür (500 hatası verme)
        api_logger.error(f"Error generating recommendations: {str(e)}", user_id=student_id, error=str(e))
        
        try:
            student = db.query(Student).filter(Student.id == student_id).first()
            if not student:
                # Öğrenci yoksa bile popüler bölümleri döndür
                student = None
            
            from schemas.university import DepartmentWithUniversityResponse
            
            # ✅ min_score None olan bölümleri filtreleme dışında bırak
            popular_query = db.query(Department).filter(
                Department.min_score.isnot(None),
                Department.min_score > 0
            )
            
            # ✅ KESİN FİLTRE (Hard Filter): Öğrencinin alan türüne uygun popüler bölümleri getir
            # Özel Durum: Eğer öğrenci TYT (Önlisans) istiyorsa, sadece TYT bölümleri
            if student:
                if student.exam_type and student.exam_type.upper() == 'TYT':
                    popular_query = popular_query.filter(
                        (Department.field_type == 'TYT') | 
                        (Department.degree_type == 'Associate') |
                        (Department.degree_type == 'Önlisans')
                    )
                elif student.field_type:
                    popular_query = popular_query.filter(Department.field_type == student.field_type)
            
            popular_departments = popular_query.order_by(
                Department.min_score.desc(),
                Department.quota.desc().nullslast()
            ).limit(20).all()
            
            if not popular_departments:
                popular_departments = db.query(Department).filter(
                    Department.min_score.isnot(None),
                    Department.min_score > 0
                ).order_by(
                    Department.min_score.desc(),
                    Department.quota.desc().nullslast()
                ).limit(20).all()
            
            university_ids = {dept.university_id for dept in popular_departments}
            universities_dict = {
                uni.id: uni
                for uni in db.query(University).filter(University.id.in_(university_ids)).all()
            }
            
            fallback_result = []
            for dept in popular_departments:
                university = universities_dict.get(dept.university_id)
                if not university:
                    continue
                
                department_response = DepartmentWithUniversityResponse(
                    **dept.__dict__,
                    university=university
                )
                
                student_score = (
                    float(student.total_score)
                    if student and student.total_score is not None
                    else 200.0
                )
                score_gap = abs(float(dept.min_score or 0) - student_score)
                compatibility_score = round(max(25.0, min(90.0, 100.0 - score_gap * 1.2)), 1)
                success_probability = round(max(10.0, min(92.0, 85.0 - max(0.0, float((dept.min_score or 0) - student_score)) * 1.1)), 1)
                preference_score = round(max(35.0, compatibility_score - 8.0), 1)
                final_score = round(
                    compatibility_score * 0.50
                    + success_probability * 0.30
                    + preference_score * 0.20,
                    1,
                )

                fallback_result.append(RecommendationResponse(
                    student_id=student_id if student else 0,
                    department_id=dept.id,
                    department=department_response,
                    compatibility_score=compatibility_score,
                    success_probability=success_probability,
                    preference_score=preference_score,
                    final_score=final_score,
                    recommendation_reason="Hedef dışı önerilen bölüm (genel popülerlik + puan yakınlığı)",
                    is_safe_choice=final_score >= 75,
                    is_dream_choice=final_score < 55,
                    is_realistic_choice=55 <= final_score < 75
                ))
            
            api_logger.info("Returning popular departments after error", user_id=student_id, count=len(fallback_result))
            return fallback_result
        except Exception as fallback_error:
            # Son çare: Boş liste döndür (ama 500 hatası verme)
            api_logger.error(f"Fallback also failed: {str(fallback_error)}", user_id=student_id, error=str(fallback_error))
            return []


@router.get("/student/{student_id}", response_model=List[RecommendationResponse])
async def get_student_recommendations(
    student_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    recommendation_type: Optional[str] = Query(None, description="safe, dream, realistic"),
    city: Optional[str] = Query(None, description="Şehir filtresi"),
    university_type: Optional[str] = Query(None, description="Üniversite türü: state, foundation"),
    has_scholarship: Optional[bool] = Query(None, description="Burs durumu"),
    db: Session = Depends(get_db)
):
    """
    Öğrencinin mevcut önerilerini getir - Direkt List döndürür (Flutter uyumlu)
    ✅ BULLETPROOF: Herhangi bir hata durumunda fallback mekanizması devreye girer
    """
    from models import Department, University
    from schemas.university import DepartmentWithUniversityResponse
    
    try:
        # Öğrenci var mı kontrol et
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            # Öğrenci yoksa bile fallback ile devam et (404 verme)
            api_logger.warning(f"Student {student_id} not found, using fallback", user_id=student_id)
            student = None
        
        # Öğrenci varsa normal akışı dene
        if student:
            query = db.query(Recommendation).filter(Recommendation.student_id == student_id)
            
            # Öneri türüne göre filtrele
            if recommendation_type == "safe":
                query = query.filter(Recommendation.is_safe_choice == True)
            elif recommendation_type == "dream":
                query = query.filter(Recommendation.is_dream_choice == True)
            elif recommendation_type == "realistic":
                query = query.filter(Recommendation.is_realistic_choice == True)
            
            # Final skora göre sırala
            query = query.order_by(Recommendation.final_score.desc())
            
            recommendations = query.offset(skip).limit(limit).all()
            
            # ✅ N+1 problemini çöz: Tüm department ve university'leri tek seferde çek
            department_ids = {rec.department_id for rec in recommendations}
            departments_dict = {
                dept.id: dept
                for dept in db.query(Department).filter(Department.id.in_(department_ids)).all()
            }
            
            university_ids = {dept.university_id for dept in departments_dict.values()}
            universities_dict = {
                uni.id: uni
                for uni in db.query(University).filter(University.id.in_(university_ids)).all()
            }
            
            # Response formatına çevir
            result = []
            for rec in recommendations:
                try:
                    department = departments_dict.get(rec.department_id)
                    if not department:
                        continue
                    
                    # ✅ KESİN FİLTRE (Hard Filter): Öğrencinin alanına uygun olmayan bölümleri filtrele
                    if student:
                        # TYT kontrolü
                        if student.exam_type and student.exam_type.upper() == 'TYT':
                            # TYT öğrencisi için sadece TYT bölümleri
                            if department.field_type != 'TYT' and department.degree_type not in ['Associate', 'Önlisans', 'onlisans', 'önlisans']:
                                api_logger.debug(
                                    f"Skipping recommendation {rec.id} - TYT student but department is not TYT/Associate",
                                    recommendation_id=rec.id,
                                    department_id=department.id
                                )
                                continue
                        # Normal alan türü kontrolü
                        elif student.field_type and department.field_type != student.field_type:
                            api_logger.debug(
                                f"Skipping recommendation {rec.id} - field_type mismatch: student={student.field_type}, department={department.field_type}",
                                recommendation_id=rec.id,
                                department_id=department.id
                            )
                            continue
                    
                    university = universities_dict.get(department.university_id)
                    if not university:
                        continue
                    
                    # ✅ EK FİLTRELER: Şehir, Üniversite Türü, Burs Durumu
                    if city and university.city and city.lower() not in university.city.lower():
                        continue
                    if university_type:
                        if university_type == 'state' and university.university_type != 'state':
                            continue
                        if university_type == 'foundation' and university.university_type != 'foundation':
                            continue
                    if has_scholarship is not None:
                        # Burs durumu kontrolü - department veya university'de scholarship bilgisi varsa kontrol et
                        # Şimdilik basit bir kontrol, daha sonra genişletilebilir
                        pass  # TODO: Burs durumu kontrolü eklenecek
                    
                    department_response = DepartmentWithUniversityResponse(
                        **department.__dict__,
                        university=university
                    )
                    
                    result.append(RecommendationResponse(
                        **rec.__dict__,
                        department=department_response
                    ))
                except Exception as rec_error:
                    # Tek bir recommendation hatası tüm listeyi bozmasın
                    api_logger.warning(f"Error processing recommendation {rec.id}: {rec_error}", user_id=student_id)
                    continue
            
            # ✅ Eğer öneri bulunduysa döndür
            if result and len(result) > 0:
                return result

            # Hedef/tercih varsa fallback ile hedef dışı bölüm doldurma.
            has_target_labels = _student_has_target_labels(student, db)

            if has_target_labels:
                api_logger.info(
                    "No cached recommendations after filters; skipping popular fallback due active target preferences",
                    user_id=student_id,
                )
                return []
        
        # ✅ FALLBACK: Eğer öneri yoksa veya hata varsa popüler bölümleri döndür
        api_logger.info("Using fallback: returning popular departments", user_id=student_id)
        
        # ✅ min_score None olan bölümleri filtreleme dışında bırak
        popular_query = db.query(Department).filter(
            Department.min_score.isnot(None),
            Department.min_score > 0
        )
        
        # ✅ KESİN FİLTRE (Hard Filter): Öğrencinin alan türüne uygun popüler bölümleri getir
        # Özel Durum: Eğer öğrenci TYT (Önlisans) istiyorsa, sadece TYT bölümleri
        if student:
            if student.exam_type and student.exam_type.upper() == 'TYT':
                popular_query = popular_query.filter(
                    (Department.field_type == 'TYT') | 
                    (Department.degree_type == 'Associate') |
                    (Department.degree_type == 'Önlisans')
                )
            elif student.field_type:
                popular_query = popular_query.filter(Department.field_type == student.field_type)
        
        popular_departments = popular_query.order_by(
            Department.min_score.desc(),  # En yüksek puanlılar önce
            Department.quota.desc().nullslast()  # Sonra kontenjanı yüksek olanlar
        ).limit(20).all()  # Maksimum 20 bölüm
        
        if not popular_departments:
            # Eğer alan türüne uygun yoksa, tüm popüler bölümleri getir
            popular_departments = db.query(Department).filter(
                Department.min_score.isnot(None),
                Department.min_score > 0
            ).order_by(
                Department.min_score.desc(),
                Department.quota.desc().nullslast()
            ).limit(20).all()
        
        # University'leri çek
        university_ids = {dept.university_id for dept in popular_departments}
        universities_dict = {
            uni.id: uni
            for uni in db.query(University).filter(University.id.in_(university_ids)).all()
        }
        
        # Response formatına çevir (dummy RecommendationResponse oluştur)
        result = []
        for dept in popular_departments:
            try:
                university = universities_dict.get(dept.university_id)
                if not university:
                    continue
                
                department_response = DepartmentWithUniversityResponse(
                    **dept.__dict__,
                    university=university
                )
                
                # Dummy recommendation oluştur (sabit 50 yerine daha anlamlı yedek skor)
                result.append(RecommendationResponse(
                    student_id=student_id if student else 0,
                    department_id=dept.id,
                    department=department_response,
                    compatibility_score=85.0,
                    success_probability=80.0,
                    preference_score=75.0,
                    final_score=85.0,
                    recommendation_reason="Popüler Bölüm (Öneri Sistemi Yedek Modu)",
                    is_safe_choice=True,
                    is_dream_choice=False,
                    is_realistic_choice=False
                ))
            except Exception as dept_error:
                # Tek bir department hatası tüm listeyi bozmasın
                api_logger.warning(f"Error processing department {dept.id}: {dept_error}", user_id=student_id)
                continue
        
        # ✅ Direkt List döndür (Flutter uyumlu) - Dict wrapper yok
        return result if result else []  # En kötü durumda boş liste döndür
        
    except Exception as e:
        # ✅ BULLETPROOF FALLBACK: Herhangi bir hata durumunda acil durum planı
        api_logger.error(f"⚠️ ÖNERİ ALGORİTMASI HATASI: {str(e)}", user_id=student_id, error=str(e))
        print(f"⚠️ ÖNERİ ALGORİTMASI HATASI: {str(e)}")
        import traceback
        traceback.print_exc()
        
        try:
            # ACİL DURUM PLANI: Veritabanından en popüler 20 bölümü çek
            fallback_deps = db.query(Department).filter(
                Department.min_score.isnot(None),
                Department.min_score > 0
            ).order_by(
                Department.min_score.desc()
            ).limit(20).all()
            
            if not fallback_deps:
                # Eğer min_score olan yoksa, herhangi bir bölümü al
                fallback_deps = db.query(Department).limit(20).all()
            
            if not fallback_deps:
                # En kötü durum: Boş liste döndür (ama 500 hatası verme)
                return []
            
            # University'leri çek
            university_ids = {dept.university_id for dept in fallback_deps}
            universities_dict = {
                uni.id: uni
                for uni in db.query(University).filter(University.id.in_(university_ids)).all()
            }
            
            # Department objelerini Recommendation formatına çevirip döndür
            result = []
            for dep in fallback_deps:
                try:
                    university = universities_dict.get(dep.university_id)
                    if not university:
                        continue
                    
                    department_response = DepartmentWithUniversityResponse(
                        **dep.__dict__,
                        university=university
                    )
                    
                    result.append(RecommendationResponse(
                        student_id=student_id,
                        department_id=dep.id,
                        department=department_response,
                        compatibility_score=85.0,
                        success_probability=85.0,
                        preference_score=85.0,
                        final_score=85.0,
                        recommendation_reason="Popüler Bölüm (Öneri Sistemi Yedek Modu)",
                        is_safe_choice=False,
                        is_dream_choice=False,
                        is_realistic_choice=True
                    ))
                except Exception as fallback_error:
                    api_logger.warning(f"Error in fallback processing department {dep.id}: {fallback_error}")
                    continue
            
            return result if result else []
            
        except Exception as fallback_fatal_error:
            # Fallback de başarısız olursa boş liste döndür (ama 500 hatası verme)
            api_logger.error(f"Fallback also failed: {str(fallback_fatal_error)}", user_id=student_id, error=str(fallback_fatal_error))
            print(f"❌ Fallback de başarısız: {str(fallback_fatal_error)}")
            return []


@router.get("/{recommendation_id}", response_model=RecommendationResponse)
async def get_recommendation(recommendation_id: int, db: Session = Depends(get_db)):
    """Belirli bir öneriyi getir"""
    recommendation = db.query(Recommendation).filter(Recommendation.id == recommendation_id).first()
    if not recommendation:
        raise HTTPException(status_code=404, detail="Öneri bulunamadı")
    
    # Department ve University bilgilerini getir
    from models import Department, University
    from schemas.university import DepartmentWithUniversityResponse
    
    department = db.query(Department).filter(Department.id == recommendation.department_id).first()
    university = db.query(University).filter(University.id == department.university_id).first()
    
    department_response = DepartmentWithUniversityResponse(
        **department.__dict__,
        university=university
    )
    
    return RecommendationResponse(
        **recommendation.__dict__,
        department=department_response
    )


@router.get("/goal-proximity/{student_id}/{department_id}")
async def get_goal_proximity(
    student_id: int,
    department_id: int,
    db: Session = Depends(get_db)
):
    """Öğrencinin seçilen bölüme hedef yakınlığını döndürür.
    TYT/AYT hedefleri yoksa toplam puan vs bölüm min_score üzerinden yaklaşık yakınlık verir.
    """
    from models import Department

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")

    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Bölüm bulunamadı")

    target_tyt = 0.0
    target_ayt = 0.0
    # ✅ min_score None kontrolü: Eğer min_score None ise, 0.0 kullan
    if getattr(department, 'min_score', None) is not None and department.min_score > 0:
        target_ayt = float(department.min_score)

    try:
        proximity = ScoreCalculator.calculate_goal_proximity(
            student_tyt_score=float(student.tyt_total_score or 0.0),
            student_ayt_score=float(student.ayt_total_score or 0.0),
            target_tyt_score=target_tyt,
            target_ayt_score=target_ayt,
        )
    except Exception:
        overall = 0.0
        # ✅ min_score None kontrolü: Eğer min_score None ise, hesaplama yapma
        if getattr(department, 'min_score', None) is not None and department.min_score > 0:
            student_score = float(student.total_score or 0.0)
            dept_score = float(department.min_score)
            if dept_score > 0:
                overall = min(100.0, (student_score / dept_score) * 100.0)
        
        # ✅ min_score None ise gap hesaplama yapma
        dept_score = float(department.min_score) if (getattr(department, 'min_score', None) is not None and department.min_score > 0) else 0.0
        student_score = float(student.total_score or 0.0)
        
        proximity = {
            'tyt_proximity': 0.0,
            'ayt_proximity': round(overall, 2),
            'overall_proximity': round(overall, 2),
            'tyt_gap': 0.0,
            'ayt_gap': round(dept_score - student_score, 2) if dept_score > 0 else 0.0,
            'is_ready': student_score >= dept_score if dept_score > 0 else False,
        }

    api_logger.info("Goal proximity calculated", user_id=student_id, department_id=department_id)
    return proximity


@router.delete("/student/{student_id}")
async def clear_student_recommendations(student_id: int, db: Session = Depends(get_db)):
    """Öğrencinin tüm önerilerini temizle"""
    # Öğrenci var mı kontrol et
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    
    # Önerileri sil
    db.query(Recommendation).filter(Recommendation.student_id == student_id).delete()
    db.commit()
    
    return {"message": "Öğrencinin tüm önerileri temizlendi"}


@router.delete("/{recommendation_id}")
async def delete_recommendation(recommendation_id: int, db: Session = Depends(get_db)):
    """Belirli bir öneriyi sil"""
    recommendation = db.query(Recommendation).filter(Recommendation.id == recommendation_id).first()
    if not recommendation:
        raise HTTPException(status_code=404, detail="Öneri bulunamadı")
    
    db.delete(recommendation)
    db.commit()
    
    return {"message": "Öneri başarıyla silindi"}


@router.get("/stats/{student_id}")
async def get_recommendation_stats(student_id: int, db: Session = Depends(get_db)):
    """Öğrencinin öneri istatistiklerini getir"""
    # Öğrenci var mı kontrol et
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    
    # İstatistikleri hesapla
    total_recommendations = db.query(Recommendation).filter(Recommendation.student_id == student_id).count()
    safe_choices = db.query(Recommendation).filter(
        Recommendation.student_id == student_id,
        Recommendation.is_safe_choice == True
    ).count()
    dream_choices = db.query(Recommendation).filter(
        Recommendation.student_id == student_id,
        Recommendation.is_dream_choice == True
    ).count()
    realistic_choices = db.query(Recommendation).filter(
        Recommendation.student_id == student_id,
        Recommendation.is_realistic_choice == True
    ).count()
    
    # Ortalama skorları hesapla
    avg_compatibility = db.query(Recommendation).filter(Recommendation.student_id == student_id).with_entities(
        db.func.avg(Recommendation.compatibility_score)
    ).scalar() or 0
    
    avg_success = db.query(Recommendation).filter(Recommendation.student_id == student_id).with_entities(
        db.func.avg(Recommendation.success_probability)
    ).scalar() or 0
    
    avg_preference = db.query(Recommendation).filter(Recommendation.student_id == student_id).with_entities(
        db.func.avg(Recommendation.preference_score)
    ).scalar() or 0
    
    return {
        "student_id": student_id,
        "total_recommendations": total_recommendations,
        "safe_choices": safe_choices,
        "dream_choices": dream_choices,
        "realistic_choices": realistic_choices,
        "average_scores": {
            "compatibility": round(avg_compatibility, 2),
            "success_probability": round(avg_success, 2),
            "preference": round(avg_preference, 2)
        }
    }


@router.post(
    "/compatibility/{student_id}",
    response_model=PreferenceCompatibilityResponse,
)
async def get_preference_compatibility(
    student_id: int,
    payload: PreferenceCompatibilityRequest,
    db: Session = Depends(get_db),
):
    """Üniversite tercih havuzu ile AI önerileri arasındaki uyumluluğu hesapla."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")

    recommendation_rows = db.query(Recommendation).filter(
        Recommendation.student_id == student_id
    ).all()
    if not recommendation_rows:
        return PreferenceCompatibilityResponse(
            recommended_university_count=0,
            saved=PreferenceCompatibilityBucket(count=len(payload.saved_university_ids), matched=0, rate=0.0),
            liked=PreferenceCompatibilityBucket(count=len(payload.liked_university_ids), matched=0, rate=0.0),
            preferred=PreferenceCompatibilityBucket(count=len(payload.preferred_university_ids), matched=0, rate=0.0),
            rejected=PreferenceCompatibilityBucket(count=len(payload.rejected_university_ids), matched=0, rate=0.0),
        )

    department_ids = {row.department_id for row in recommendation_rows}
    department_rows = db.query(Department).filter(Department.id.in_(department_ids)).all()
    recommended_university_ids = {dep.university_id for dep in department_rows if dep.university_id is not None}

    def _bucket(ids: List[int]) -> PreferenceCompatibilityBucket:
        unique_ids = set(ids)
        count = len(unique_ids)
        matched = len(unique_ids.intersection(recommended_university_ids))
        rate = round((matched * 100.0 / count), 2) if count > 0 else 0.0
        return PreferenceCompatibilityBucket(count=count, matched=matched, rate=rate)

    return PreferenceCompatibilityResponse(
        recommended_university_count=len(recommended_university_ids),
        saved=_bucket(payload.saved_university_ids),
        liked=_bucket(payload.liked_university_ids),
        preferred=_bucket(payload.preferred_university_ids),
        rejected=_bucket(payload.rejected_university_ids),
    )

