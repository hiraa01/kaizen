# -*- coding: utf-8 -*-
"""
✅ GELIŞMIŞ AĞIRLIKLI PUANLAMA SİSTEMİ
Yapay zeka destekli tercih öneri motoru - Ağırlıklı Puan ile
"""
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from models import Student, Department, University, Recommendation, Preference
from schemas.university import RecommendationResponse, DepartmentWithUniversityResponse, UniversityResponse
from core.logging_config import recommendation_logger
from core.exceptions import RecommendationError, StudentNotFoundError
import json
import unicodedata


class RecommendationEngine:
    """
    ✅ GELIŞMIŞ AĞIRLIKLI PUANLAMA SİSTEMİ
    Yapay zeka destekli tercih öneri motoru - Ağırlıklı Puan ile
    """
    
    # ✅ SCORING PARAMETERS
    BASE_SCORE = 50.0  # Taban puan (her bölüm minimum bu puanı alır)
    SCORE_PROXIMITY_MAX = 30.0  # Puan yakınlığından maksimum bonus
    CITY_PREFERENCE_BONUS = 20.0  # Tercih edilen şehir bonusu
    INTEREST_AREA_BONUS = 15.0  # İlgi alanı eşleşme bonusu
    UNIVERSITY_PREFERENCE_BONUS = 12.0  # Kullanıcının beğendiği/kaydettiği üniversite bonusu
    
    # ✅ HARD FILTER PARAMETERS
    SCORE_LOWER_MARGIN = -40.0  # Alt sınır: öğrenci puanı - 40
    SCORE_UPPER_MARGIN = 30.0   # Üst sınır: öğrenci puanı + 30

    @staticmethod
    def _clamp_score(value: float, min_value: float = 0.0, max_value: float = 100.0) -> float:
        """Keep user-facing scores in 0-100 range."""
        return max(min_value, min(max_value, float(value)))
    
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _department_matches_target_labels(
        dept: Department, labels: List[str]
    ) -> bool:
        """True if department name or normalized_name contains any target label (substring, lowercase)."""
        def normalize(text: str) -> str:
            lowered = (text or "").casefold().strip()
            # Turkish-i / combining-dot issues: "DİŞ" -> "diş" and "di̇ş" normalize equally.
            lowered = (
                lowered
                .replace("ı", "i")
                .replace("ş", "s")
                .replace("ğ", "g")
                .replace("ü", "u")
                .replace("ö", "o")
                .replace("ç", "c")
            )
            normalized = unicodedata.normalize("NFKD", lowered)
            return "".join(ch for ch in normalized if not unicodedata.combining(ch))

        blob = normalize(f"{dept.name or ''} {(dept.normalized_name or '')}")
        for raw in labels:
            token = normalize(str(raw))
            if len(token) < 2:
                continue
            if token in blob:
                return True
        return False

    @staticmethod
    def _parse_preferred_department_labels(student: Student) -> List[str]:
        if not student.preferred_departments:
            return []
        try:
            raw = (
                json.loads(student.preferred_departments)
                if isinstance(student.preferred_departments, str)
                else student.preferred_departments
            )
            if isinstance(raw, list):
                return [str(x).strip() for x in raw if x and str(x).strip()]
        except (json.JSONDecodeError, TypeError):
            return []
        return []

    def _get_target_labels_from_preferences(self, student_id: int) -> List[str]:
        """Collect target labels from /targets (Preference) rows."""
        rows = (
            self.db.query(Department.name, Department.normalized_name)
            .join(Preference, Preference.department_id == Department.id)
            .filter(Preference.student_id == student_id)
            .all()
        )
        labels: List[str] = []
        for name, normalized_name in rows:
            if isinstance(name, str) and name.strip():
                labels.append(name.strip())
            if isinstance(normalized_name, str) and normalized_name.strip():
                labels.append(normalized_name.strip())
        return labels
    
    @staticmethod
    def _get_university_logo_url(university: University) -> Optional[str]:
        """Üniversite logosu URL'i oluştur"""
        if university.website:
            domain = university.website.replace('http://', '').replace('https://', '').replace('www.', '').split('/')[0]
            return f"https://www.google.com/s2/favicons?domain={domain}&sz=256"
        return None
    
    def generate_recommendations(
        self,
        student_id: int,
        limit: int = 50,
        weights: Optional[Tuple[float, float, float]] = None,  # Backward compatibility (ignored in new system)
        preferred_university_ids: Optional[set[int]] = None,
    ) -> List[RecommendationResponse]:
        """
        ✅ YENI ALGORİTMA: Ağırlıklı Puanlama Sistemi
        
        1. Veri Çekme: Öğrenci ve tüm bölümleri çek
        2. Hard Filter:
           - field_type eşleştir
           - min_score: öğrenci puanı ± sınırlar içinde
        3. Scoring:
           - Baz puan: 50
           - Puan yakınlığı: Fark azaldıkça +0 ile +30
           - Şehir: Tercih edilen şehirdeyse +20
           - İlgi: İlgi alanı sözcükleri eşleşiyorsa +15
        4. Sıralama: Top 20
        """
        try:
            recommendation_logger.info(
                "Starting recommendation generation (Weighted Scoring System)",
                user_id=student_id,
                limit=limit
            )
            
            # ✅ STEP 1: Öğrenci bilgisini çek
            student = self.db.query(Student).filter(Student.id == student_id).first()
            if not student:
                recommendation_logger.warning(
                    "Student not found for recommendation generation",
                    user_id=student_id
                )
                raise StudentNotFoundError(f"Student with ID {student_id} not found")
            
            # ✅ KESİN FİLTRE: Öğrencinin alan türü belirtilmiş mi?
            if not student.field_type or student.field_type.strip() == '':
                raise StudentNotFoundError(f"Student {student_id} has no field_type")
            
            # Öğrencinin referans puanını al
            student_score = student.total_score if student.total_score and student.total_score > 0 else 200.0
            
            recommendation_logger.info(
                f"Student score for filtering: {student_score}, field_type: {student.field_type}",
                user_id=student_id,
                student_score=student_score,
                field_type=student.field_type
            )
            
            # ✅ STEP 2: Tercih edilen şehirleri ve ilgi alanlarını al (RAG)
            preferred_cities = []
            if student.preferred_cities:
                try:
                    preferred_cities = json.loads(student.preferred_cities) if isinstance(student.preferred_cities, str) else student.preferred_cities
                except (json.JSONDecodeError, TypeError):
                    preferred_cities = []
            
            interest_areas = []
            if student.interest_areas:
                try:
                    interest_areas = json.loads(student.interest_areas) if isinstance(student.interest_areas, str) else student.interest_areas
                except (json.JSONDecodeError, TypeError):
                    interest_areas = []
            
            # Interest areas'ı normalize et (lowercase ve split)
            interest_keywords = set()
            for area in interest_areas:
                if isinstance(area, str):
                    # Kelimeyi parçala (örn: "Elektrik Mühendisliği" -> "elektrik", "mühendisliği")
                    for word in area.lower().split():
                        if len(word) > 2:  # 2 karakterden uzun kelimeleri al
                            interest_keywords.add(word.strip())
            
            profile_department_labels = self._parse_preferred_department_labels(student)
            target_labels_from_preferences = self._get_target_labels_from_preferences(
                student_id
            )
            target_department = getattr(student, "target_department", None)

            # Profile preferred_departments varsa bunu kaynak gerçek kabul et.
            # Böylece eski /targets kayıtları yeni hedefi kirletmez.
            preferred_department_labels: List[str] = list(profile_department_labels)
            if target_department and str(target_department).strip():
                preferred_department_labels.append(str(target_department).strip())

            if not preferred_department_labels and target_labels_from_preferences:
                preferred_department_labels = list(target_labels_from_preferences)

            recommendation_logger.info(
                f"Student preferences: {len(preferred_cities)} cities, {len(interest_keywords)} interest keywords, "
                f"{len(preferred_department_labels)} target department labels",
                user_id=student_id,
                preferred_cities=preferred_cities,
                interest_keywords=list(interest_keywords)[:5],  # İlk 5 göster
                target_department_labels=preferred_department_labels[:10],
            )
            if preferred_university_ids is None:
                preferred_university_ids = set()
            
            # ✅ STEP 3: Hard Filter - Uygun bölümleri getir
            # Öğrencinin alan türüne uygun bölümleri getir
            field_departments = self.db.query(Department).filter(
                Department.field_type == student.field_type,
                Department.min_score.isnot(None),  # min_score None değilse
                Department.min_score > 0  # min_score > 0
            ).all()
            
            recommendation_logger.info(
                f"Found {len(field_departments)} departments with matching field_type",
                user_id=student_id,
                total_departments=len(field_departments)
            )
            
            # ✅ STEP 4: Hedef varsa önce hedef bölüm eşleşmesi (puan bandından bağımsız)
            # Bu sayede kullanıcı "Diş Hekimliği" seçtiğinde, puan bandı dar olsa bile
            # hedef dışı popüler bölümler yerine diş hekimliği programları önerilir.
            if preferred_department_labels:
                matched_targets = [
                    d
                    for d in field_departments
                    if self._department_matches_target_labels(
                        d, preferred_department_labels
                    )
                ]
                if matched_targets:
                    departments = matched_targets
                    recommendation_logger.info(
                        "Using target-matched departments from full field pool",
                        user_id=student_id,
                        remaining_departments=len(departments),
                    )
                else:
                    departments = []
                    recommendation_logger.warning(
                        "preferred_departments matched no program names; empty recommendation set",
                        user_id=student_id,
                        labels=preferred_department_labels,
                    )
            else:
                # ✅ STEP 4b: Hedef yoksa klasik puan bandı filtresi
                filtered_depts = []
                for dept in field_departments:
                    score_diff = dept.min_score - student_score
                    # Her iki yönde de sınırları kontrol et
                    if self.SCORE_LOWER_MARGIN <= score_diff <= self.SCORE_UPPER_MARGIN:
                        filtered_depts.append(dept)
                    else:
                        recommendation_logger.debug(
                            f"Department {dept.id} filtered out - score {dept.min_score} not in range [{student_score + self.SCORE_LOWER_MARGIN}, {student_score + self.SCORE_UPPER_MARGIN}]",
                            department_id=dept.id,
                            student_score=student_score,
                            dept_score=dept.min_score
                        )

                if not filtered_depts and field_departments:
                    recommendation_logger.warning(
                        "No departments in score band; using closest min_score fallback",
                        user_id=student_id,
                        student_score=student_score,
                    )
                    filtered_depts = sorted(
                        field_departments,
                        key=lambda d: abs(float(d.min_score) - float(student_score)),
                    )[: max(limit, 30)]

                departments = filtered_depts
            
            recommendation_logger.info(
                f"After score filtering: {len(departments)} departments remain",
                user_id=student_id,
                remaining_departments=len(departments)
            )
            
            # ✅ STEP 5: Üniversite bilgisini çek (şehir için)
            university_ids = {dept.university_id for dept in departments}
            universities_dict = {
                uni.id: uni
                for uni in self.db.query(University).filter(University.id.in_(university_ids)).all()
            } if university_ids else {}
            
            # ✅ STEP 6: Scoring - Her bölüm için match_score hesapla
            scoring_results = []
            
            for dept in departments:
                # Baz puan (sıralama için eski ağırlıklı yaklaşım korunuyor)
                match_score = self.BASE_SCORE
                
                # ✅ Scoring A: Puan Yakınlığı (0 ile +30 arası)
                # Puan farkı 0'a yaklaştıkça daha yüksek puan
                score_diff = abs(dept.min_score - student_score)
                
                # 0-20 fark: +30 puan
                # 20-40 fark: +20 puan
                # 40+ fark: +10 puan
                if score_diff <= 20:
                    match_score += 30.0
                elif score_diff <= 40:
                    match_score += 20.0
                else:
                    match_score += 10.0
                
                proximity_score = match_score - self.BASE_SCORE  # Sadece eklenen kısım
                
                # ✅ Scoring B: Şehir Uyumu (+20)
                city_bonus = 0.0
                university = universities_dict.get(dept.university_id)
                if university and university.city and preferred_cities:
                    city_normalized = university.city.lower().strip()
                    if any(pref_city.lower().strip() == city_normalized for pref_city in preferred_cities):
                        match_score += self.CITY_PREFERENCE_BONUS
                        city_bonus = self.CITY_PREFERENCE_BONUS
                
                # ✅ Scoring C: Bölüm İlgisi (+15)
                interest_bonus = 0.0
                if interest_keywords:
                    dept_name_lower = dept.name.lower() if dept.name else ""
                    matched_keywords = 0
                    for keyword in interest_keywords:
                        if keyword in dept_name_lower:
                            matched_keywords += 1
                    
                    if matched_keywords > 0:
                        match_score += self.INTEREST_AREA_BONUS
                        interest_bonus = self.INTEREST_AREA_BONUS

                # ✅ Scoring D: Üniversite tercih sinyali (+12)
                university_bonus = 0.0
                if university and university.id in preferred_university_ids:
                    match_score += self.UNIVERSITY_PREFERENCE_BONUS
                    university_bonus = self.UNIVERSITY_PREFERENCE_BONUS
                
                compatibility_score = round(self._clamp_score(match_score), 1)
                success_probability = round(max(0.0, min(100.0, 60.0 + proximity_score)), 1)
                preference_score = round(
                    max(
                        0.0,
                        min(100.0, 50.0 + interest_bonus + university_bonus + (city_bonus * 0.5)),
                    ),
                    1,
                )
                final_score = round(self._clamp_score(match_score), 1)

                scoring_results.append({
                    'department': dept,
                    'match_score': round(match_score, 2),
                    'proximity_score': round(proximity_score, 2),
                    'city_bonus': round(city_bonus, 2),
                    'interest_bonus': round(interest_bonus, 2),
                    'university_bonus': round(university_bonus, 2),
                    'compatibility_score': compatibility_score,
                    'success_probability': success_probability,
                    'preference_score': preference_score,
                    'final_score': final_score,
                })
            
            recommendation_logger.info(
                f"Scored {len(scoring_results)} departments",
                user_id=student_id,
                scored_count=len(scoring_results)
            )
            
            # ✅ STEP 7: Sıralama - En yüksek match_score'a göre sırala
            scoring_results.sort(key=lambda x: x['final_score'], reverse=True)
            
            # ✅ STEP 8: Top 20'yi seç
            top_results = scoring_results[:min(limit, 20)]
            
            recommendation_logger.info(
                f"Top {len(top_results)} recommendations selected",
                user_id=student_id,
                top_count=len(top_results)
            )
            
            # ✅ STEP 9: Önerileri kaydet ve response formatına dönüştür
            # Önce eski önerileri sil
            self.db.query(Recommendation).filter(Recommendation.student_id == student_id).delete()
            self.db.commit()
            
            result = []
            for i, scored_item in enumerate(top_results):
                dept = scored_item['department']
                final_score = scored_item['final_score']
                compatibility_score = scored_item['compatibility_score']
                success_probability = scored_item['success_probability']
                preference_score = scored_item['preference_score']
                score_gap = round(float(dept.min_score or 0.0) - float(student_score), 2)
                
                # Veritabanına kaydet
                try:
                    recommendation = Recommendation(
                        student_id=student_id,
                        department_id=dept.id,
                        compatibility_score=compatibility_score,
                        success_probability=success_probability,
                        preference_score=preference_score,
                        final_score=final_score,
                        recommendation_reason=(
                            f"Uyum {compatibility_score:.0f}% • Başarı Olasılığı {success_probability:.0f}% • "
                            f"Tercih Eşleşmesi {preference_score:.0f}% • "
                            f"Taban Puan {float(dept.min_score or 0.0):.2f} • "
                            f"Puan Farkı {score_gap:+.2f}"
                        ),
                        is_safe_choice=final_score >= 75,
                        is_dream_choice=final_score < 55,
                        is_realistic_choice=55 <= final_score < 75
                    )
                    self.db.add(recommendation)
                    self.db.flush()
                except Exception as e:
                    recommendation_logger.warning(
                        f"Could not save recommendation for department {dept.id}: {str(e)}",
                        department_id=dept.id,
                        error=str(e)
                    )
                    continue
                
                # Response formatına dönüştür
                university = universities_dict.get(dept.university_id)
                if not university:
                    continue
                
                logo_url = self._get_university_logo_url(university)
                
                university_response = UniversityResponse(
                    id=university.id,
                    name=university.name,
                    city=university.city,
                    university_type=university.university_type,
                    website=university.website,
                    established_year=university.established_year,
                    latitude=university.latitude,
                    longitude=university.longitude,
                    created_at=university.created_at,
                    updated_at=university.updated_at,
                    logo_url=logo_url
                )
                
                department_response = DepartmentWithUniversityResponse(
                    id=dept.id,
                    university_id=dept.university_id,
                    name=dept.name,
                    field_type=dept.field_type,
                    language=dept.language,
                    faculty=dept.faculty,
                    duration=dept.duration,
                    degree_type=dept.degree_type,
                    min_score=dept.min_score,
                    min_rank=dept.min_rank,
                    quota=dept.quota,
                    scholarship_quota=dept.scholarship_quota,
                    tuition_fee=dept.tuition_fee,
                    has_scholarship=dept.has_scholarship,
                    last_year_min_score=dept.last_year_min_score,
                    last_year_min_rank=dept.last_year_min_rank,
                    last_year_quota=dept.last_year_quota,
                    description=dept.description,
                    requirements=dept.requirements,
                    created_at=dept.created_at,
                    updated_at=dept.updated_at,
                    university=university_response
                )
                
                rec_response = RecommendationResponse(
                    id=recommendation.id if hasattr(recommendation, 'id') else None,
                    student_id=student_id,
                    department_id=dept.id,
                    compatibility_score=compatibility_score,
                    success_probability=success_probability,
                    preference_score=preference_score,
                    final_score=final_score,
                    recommendation_reason=recommendation.recommendation_reason,
                    is_safe_choice=recommendation.is_safe_choice,
                    is_dream_choice=recommendation.is_dream_choice,
                    is_realistic_choice=recommendation.is_realistic_choice,
                    created_at=recommendation.created_at if hasattr(recommendation, 'created_at') else None,
                    department=department_response
                )
                
                result.append(rec_response)
            
            self.db.commit()
            
            recommendation_logger.info(
                f"Recommendation generation completed successfully",
                user_id=student_id,
                total_recommendations=len(result)
            )
            
            return result
            
        except StudentNotFoundError:
            recommendation_logger.error("Student not found", user_id=student_id)
            raise
        except Exception as e:
            recommendation_logger.error(f"Error generating recommendations: {str(e)}", user_id=student_id, error_type=type(e).__name__)
            self.db.rollback()
            raise RecommendationError(f"Tercih önerileri oluşturulurken bir hata oluştu: {str(e)}")

