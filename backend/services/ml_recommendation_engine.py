"""
Makine öğrenmesi destekli öneri motoru
Bu modül, geçmiş verilerle eğitilmiş modeller kullanarak daha akıllı öneriler sunar
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from xgboost import XGBRegressor
from typing import List, Dict, Any, Tuple, Optional
import joblib
import os
import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
from models import Student, Department, Recommendation, University
from core.logging_config import recommendation_logger

class MLRecommendationEngine:
    """Makine öğrenmesi destekli öneri motoru"""
    
    def __init__(self, db: Session):
        self.db = db
        self.models = {}
        self.scalers = {}
        self.is_trained = False
        # Docker volume'da ml_models, local'de models/ kullanılır
        self.model_path = os.getenv("ML_MODELS_PATH", "models/")
        # Docker volume kontrolü
        if os.path.exists("/app/ml_models"):
            self.model_path = "/app/ml_models/"
        elif os.path.exists("ml_models"):
            self.model_path = "ml_models/"
        
        # Son eğitimin gerçek regresyon metrikleri (RMSE/MAE/R2) - sadece R2 değil
        self.last_training_metrics: Dict[str, Any] = {}

        # Model dosyalarını yükle
        self._load_models()
    
    def train_models(self, training_data: List[Dict[str, Any]]):
        """Modelleri eğit"""
        try:
            recommendation_logger.info("Starting ML model training", data_size=len(training_data))
            
            # Veriyi DataFrame'e çevir
            df = pd.DataFrame(training_data)
            
            # Özellik mühendisliği
            X, y = self._prepare_features(df)
            
            # Modelleri eğit
            self._train_compatibility_model(X, y['compatibility'])
            self._train_success_model(X, y['success_probability'])
            self._train_preference_model(X, y['preference'])
            
            # Modelleri kaydet
            self._save_models()

            # Gerçek regresyon metriklerini (RMSE/MAE/R2) diske yaz - R2 tek başına yanıltıcı
            try:
                metrics_report = {
                    "trained_at": datetime.now(timezone.utc).isoformat(),
                    "n_samples": len(training_data),
                    "models": self.last_training_metrics,
                    "note": (
                        "Bu eğitim verisi sentetik/kural tabanlı etiketlerle üretildiyse, "
                        "bu metrikler gerçek yerleşme/isabet oranini GOSTERMEZ; sadece modelin "
                        "etiketleme kuralini ne kadar iyi ogrendigini gosterir."
                    ),
                }
                os.makedirs(self.model_path, exist_ok=True)
                metrics_path = os.path.join(self.model_path, "training_metrics.json")
                with open(metrics_path, "w", encoding="utf-8") as f:
                    json.dump(metrics_report, f, ensure_ascii=False, indent=2)
                recommendation_logger.info("Training metrics saved", path=metrics_path)
            except Exception as metrics_err:
                recommendation_logger.warning("Could not persist training metrics", error=str(metrics_err))

            self.is_trained = True
            recommendation_logger.info("ML models trained successfully")
            
        except Exception as e:
            recommendation_logger.error("ML training failed", error=str(e))
            raise
    
    def generate_recommendations(
        self,
        student_id: int,
        limit: int = 50,
        weights: Tuple[float, float, float] | None = None
    ) -> List[Dict[str, Any]]:
        """ML destekli öneriler oluştur"""
        if not self.is_trained:
            recommendation_logger.warning("Models not trained, falling back to rule-based")
            return self._fallback_recommendations(student_id, limit)
        
        try:
            student = self.db.query(Student).filter(Student.id == student_id).first()
            if not student:
                raise ValueError(f"Student {student_id} not found")
            
            # Öğrenci özelliklerini hazırla
            student_features = self._prepare_student_features(student)
            
            # Bölümleri getir
            departments = self.db.query(Department).filter(
                Department.field_type == student.field_type
            ).all()
            
            # Ağırlıklar (compatibility, success, preference)
            if not weights:
                weights = (0.4, 0.4, 0.2)
            w_c, w_s, w_p = weights
            total_w = max(1e-9, (w_c + w_s + w_p))
            w_c, w_s, w_p = w_c / total_w, w_s / total_w, w_p / total_w

            recommendations = []
            
            for department in departments:
                # Gelişmiş özellik hazırlama (interaksiyon özellikleri dahil)
                combined_features = self._prepare_combined_features(student, department)
                combined_features = combined_features.reshape(1, -1)
                
                # Skorları tahmin et
                compatibility = self._predict_compatibility(combined_features)
                success_prob = self._predict_success_probability(combined_features)
                preference = self._predict_preference(combined_features)
                
                # Final skor
                final_score = (compatibility * w_c + success_prob * w_s + preference * w_p)
                
                # Öneri türünü belirle
                is_safe = success_prob >= 0.8
                is_dream = success_prob <= 0.3
                is_realistic = 0.3 < success_prob < 0.8
                
                # Öneri sebebi
                reason = self._generate_ml_reason(compatibility, success_prob, preference)
                
                recommendations.append({
                    'student_id': student_id,
                    'department_id': department.id,
                    'compatibility_score': float(compatibility),
                    'success_probability': float(success_prob),
                    'preference_score': float(preference),
                    'final_score': float(final_score),
                    'recommendation_reason': reason,
                    'is_safe_choice': is_safe,
                    'is_dream_choice': is_dream,
                    'is_realistic_choice': is_realistic,
                    'department': department,
                })
            
            # Skora göre sırala
            recommendations.sort(key=lambda x: x['final_score'], reverse=True)
            
            return recommendations[:limit]
            
        except Exception as e:
            recommendation_logger.error("ML recommendation failed", error=str(e))
            return self._fallback_recommendations(student_id, limit)

    def compute_aggregate_ml_signals_for_student_like(
        self,
        student_like: object,
    ) -> Dict[str, float]:
        """
        Vectorized max success probability and mean compatibility across departments
        for an object exposing the same numeric attributes as Student.
        """
        if not self.is_trained:
            return {"max_success_probability": 0.5, "mean_compatibility": 0.5}

        field_type = getattr(student_like, "field_type", None) or "SAY"
        departments = (
            self.db.query(Department)
            .options(selectinload(Department.university))
            .filter(Department.field_type == field_type)
            .all()
        )
        if not departments:
            return {"max_success_probability": 0.5, "mean_compatibility": 0.5}

        feature_rows = np.stack(
            [
                self._prepare_combined_features_with_university(
                    student_like,
                    d,
                    getattr(d, "university", None),
                )
                for d in departments
            ],
            axis=0,
        )

        success_scaled = self.scalers["success"].transform(feature_rows)
        success_preds = np.clip(self.models["success"].predict(success_scaled), 0.0, 1.0)

        compat_scaled = self.scalers["compatibility"].transform(feature_rows)
        compat_preds = np.clip(
            self.models["compatibility"].predict(compat_scaled), 0.0, 1.0
        )

        return {
            "max_success_probability": float(np.max(success_preds)),
            "mean_compatibility": float(np.mean(compat_preds)),
        }

    def _prepare_combined_features_with_university(
        self,
        student: object,
        department: Department,
        university: Optional[University],
    ) -> np.ndarray:
        """Prepare combined features without extra per-department DB queries."""
        student_features = self._prepare_student_features(student)

        university_type = (
            university.university_type
            if university and getattr(university, "university_type", None)
            else "Devlet"
        )
        university_city = (
            university.city if university and getattr(university, "city", None) else ""
        )

        dept_features = np.array(
            [
                float(department.min_score or 0.0),
                float(department.min_rank or 0.0),
                float(department.quota or 0.0),
                float(department.tuition_fee or 0.0),
                1 if bool(department.has_scholarship) else 0,
                self._encode_university_type(university_type),
                self._encode_city(university_city),
            ]
        )

        score_diff = (getattr(student, "total_score", 0) or 0) - (department.min_score or 0)
        rank_diff = (department.min_rank or 0) - (getattr(student, "rank", 0) or 0)
        score_ratio = (getattr(student, "total_score", 0) or 0) / ((department.min_score or 0) + 1e-6)
        rank_ratio = (getattr(student, "rank", 0) or 0) / ((department.min_rank or 0) + 1e-6)
        percentile_diff = (getattr(student, "percentile", 0) or 0) - (
            100 - ((department.min_rank or 0) / 1000)
        )

        math_strength = (getattr(student, "tyt_math_net", 0) or 0) + (
            getattr(student, "ayt_math_net", 0) or 0
        )
        competitiveness = (department.min_rank or 0) / ((department.quota or 1) + 1)

        preferred_cities_match = 0
        if self._parse_preference_values(getattr(student, "preferred_cities", None)):
            preferred_cities = self._parse_preference_values(
                getattr(student, "preferred_cities", None)
            )
            if university_city in preferred_cities:
                preferred_cities_match = 1

        preferred_types_match = 0
        if self._parse_preference_values(getattr(student, "preferred_university_types", None)):
            preferred_types = self._parse_preference_values(
                getattr(student, "preferred_university_types", None)
            )
            if university_type in preferred_types:
                preferred_types_match = 1

        scholarship_match = 1 if (getattr(student, "scholarship_preference", False) and department.has_scholarship) else 0

        interaction_features = np.array(
            [
                score_diff,
                rank_diff,
                score_ratio,
                rank_ratio,
                percentile_diff,
                math_strength,
                competitiveness,
                preferred_cities_match,
                preferred_types_match,
                scholarship_match,
            ]
        )

        return np.concatenate([student_features, dept_features, interaction_features])

    def _parse_preference_values(self, raw_value: object) -> List[str]:
        """Accept either JSON string or a direct list and return a clean string list."""
        if raw_value is None:
            return []
        if isinstance(raw_value, list):
            return [str(item) for item in raw_value if item is not None]
        if isinstance(raw_value, str):
            text = raw_value.strip()
            if not text:
                return []
            try:
                decoded = json.loads(text)
                if isinstance(decoded, list):
                    return [str(item) for item in decoded if item is not None]
            except Exception:
                return [text]
        return []

    def _prepare_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """Eğitim verilerini hazırla - gelişmiş feature engineering"""
        # Öğrenci özellikleri (temel)
        student_features = [
            'total_score', 'rank', 'percentile', 'tyt_total_score', 'ayt_total_score',
            'field_type_encoded', 'exam_type_encoded', 'class_level_encoded'
        ]
        
        # Bölüm özellikleri (temel)
        dept_features = [
            'min_score', 'min_rank', 'quota', 'tuition_fee', 'has_scholarship',
            'university_type_encoded', 'city_encoded'
        ]
        
        # İnteraksiyon özellikleri (derived features)
        df['score_diff'] = df['total_score'] - df['min_score']
        df['rank_diff'] = df['min_rank'] - df['rank']  # Pozitif = daha iyi
        df['score_ratio'] = df['total_score'] / (df['min_score'] + 1e-6)
        df['rank_ratio'] = df['rank'] / (df['min_rank'] + 1e-6)
        df['percentile_diff'] = df['percentile'] - (100 - (df['min_rank'] / 1000))
        
        # Öğrenci güçlü alanları (net skorları)
        if 'tyt_math_net' in df.columns:
            df['math_strength'] = df['tyt_math_net'] + df.get('ayt_math_net', 0)
        else:
            df['math_strength'] = df['tyt_total_score'] * 0.3
        
        # Bölüm popülerliği (kontenjan/sıralama oranı)
        df['department_competitiveness'] = df['min_rank'] / (df['quota'] + 1)
        
        # Tercih özellikleri (eğer varsa)
        if 'preferred_cities_match' not in df.columns:
            df['preferred_cities_match'] = 0
        if 'preferred_types_match' not in df.columns:
            df['preferred_types_match'] = 0
        if 'scholarship_match' not in df.columns:
            df['scholarship_match'] = 0
        
        # İnteraksiyon özellikleri listesi
        interaction_features = [
            'score_diff', 'rank_diff', 'score_ratio', 'rank_ratio', 
            'percentile_diff', 'math_strength', 'department_competitiveness',
            'preferred_cities_match', 'preferred_types_match', 'scholarship_match'
        ]
        
        # Tüm özellikleri birleştir
        all_features = student_features + dept_features + interaction_features
        # Sadece mevcut kolonları kullan
        available_features = [f for f in all_features if f in df.columns]
        
        # Hedef değişkenler
        targets = ['compatibility', 'success_probability', 'preference']
        
        X = df[available_features].values
        y = {target: df[target].values for target in targets}
        
        return X, y
    
    def _prepare_student_features(self, student: Student) -> np.ndarray:
        """Öğrenci özelliklerini hazırla - gelişmiş"""
        # Temel özellikler
        features = [
            student.total_score or 0,
            student.rank or 0,
            student.percentile or 0,
            student.tyt_total_score or 0,
            student.ayt_total_score or 0,
            self._encode_field_type(student.field_type),
            self._encode_exam_type(student.exam_type),
            self._encode_class_level(student.class_level),
        ]
        return np.array(features)
    
    def _prepare_department_features(self, department: Department) -> np.ndarray:
        """Bölüm özelliklerini hazırla (Üniversite bilgilerini ilişki üzerinden getirir)."""
        # University bilgilerini yükle
        university: Optional[University] = self.db.query(University).filter(University.id == department.university_id).first()
        university_type = (university.university_type if university and getattr(university, 'university_type', None) else 'Devlet')
        university_city = (university.city if university and getattr(university, 'city', None) else '')

        features = [
            float(department.min_score or 0.0),
            float(department.min_rank or 0.0),
            float(department.quota or 0.0),
            float(department.tuition_fee or 0.0),
            1 if bool(department.has_scholarship) else 0,
            self._encode_university_type(university_type),
            self._encode_city(university_city),
        ]
        return np.array(features)
    
    def _prepare_combined_features(self, student: Student, department: Department) -> np.ndarray:
        """Öğrenci ve bölüm özelliklerini birleştir ve interaksiyon özellikleri ekle"""
        student_features = self._prepare_student_features(student)
        dept_features = self._prepare_department_features(department)
        
        # İnteraksiyon özellikleri
        score_diff = (student.total_score or 0) - (department.min_score or 0)
        rank_diff = (department.min_rank or 0) - (student.rank or 0)
        score_ratio = (student.total_score or 0) / ((department.min_score or 0) + 1e-6)
        rank_ratio = (student.rank or 0) / ((department.min_rank or 0) + 1e-6)
        percentile_diff = (student.percentile or 0) - (100 - ((department.min_rank or 0) / 1000))
        
        # Öğrenci güçlü alanları
        math_strength = (student.tyt_math_net or 0) + (getattr(student, 'ayt_math_net', None) or 0)
        
        # Bölüm rekabeti
        competitiveness = (department.min_rank or 0) / ((department.quota or 1) + 1)
        
        # Tercih eşleşmeleri
        preferred_cities_match = 0
        if student.preferred_cities:
            try:
                preferred_cities = json.loads(student.preferred_cities)
                university = self.db.query(University).filter(University.id == department.university_id).first()
                if university and university.city in preferred_cities:
                    preferred_cities_match = 1
            except:
                pass
        
        preferred_types_match = 0
        if student.preferred_university_types:
            try:
                preferred_types = json.loads(student.preferred_university_types)
                university = self.db.query(University).filter(University.id == department.university_id).first()
                if university and university.university_type in preferred_types:
                    preferred_types_match = 1
            except:
                pass
        
        scholarship_match = 1 if (student.scholarship_preference and department.has_scholarship) else 0
        
        # İnteraksiyon özellikleri
        interaction_features = np.array([
            score_diff, rank_diff, score_ratio, rank_ratio, percentile_diff,
            math_strength, competitiveness, preferred_cities_match, 
            preferred_types_match, scholarship_match
        ])
        
        # Tüm özellikleri birleştir
        combined = np.concatenate([student_features, dept_features, interaction_features])
        return combined
    
    def _evaluate_model(self, name: str, model, X_train, y_train, X_test, y_test) -> Dict[str, float]:
        """Gerçek regresyon metriklerini hesapla (sadece R2 değil RMSE/MAE de).

        NOT: Bu değerler, model.score() çağrısından farklı olarak, modelin
        ÖLÇÜM BİRİMİNDE (0-1 aralığındaki skorlarda) ortalama hatasını verir ve
        model eğitiminde kullanılan etiketlerin gerçek/sentetik olmasına göre
        yorumlanmalıdır. Sentetik etiketlerle eğitilmiş bir modelde yüksek R2,
        sadece kodun kendi kuralını ne kadar iyi öğrendiğini gösterir; gerçek
        dünya isabetini göstermez.
        """
        pred_train = model.predict(X_train)
        pred_test = model.predict(X_test)

        metrics = {
            "n_train": int(len(y_train)),
            "n_test": int(len(y_test)),
            "train_rmse": float(np.sqrt(mean_squared_error(y_train, pred_train))),
            "train_mae": float(mean_absolute_error(y_train, pred_train)),
            "train_r2": float(r2_score(y_train, pred_train)),
            "test_rmse": float(np.sqrt(mean_squared_error(y_test, pred_test))),
            "test_mae": float(mean_absolute_error(y_test, pred_test)),
            "test_r2": float(r2_score(y_test, pred_test)),
        }

        recommendation_logger.info(
            f"{name} model evaluated",
            **metrics,
        )
        self.last_training_metrics[name] = metrics
        return metrics

    def _train_compatibility_model(self, X: np.ndarray, y: np.ndarray):
        """Uyumluluk modelini eğit - XGBoost ile iyileştirilmiş"""
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Özellikleri ölçeklendir
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # XGBoost Regressor (daha güçlü ve hızlı model)
        model = XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            objective='reg:squarederror',
            n_jobs=-1,  # Tüm CPU çekirdeklerini kullan
            tree_method='hist'  # Daha hızlı eğitim için
        )
        model.fit(X_train_scaled, y_train)
        
        # Modeli kaydet
        self.models['compatibility'] = model
        self.scalers['compatibility'] = scaler
        
        # Performansı logla
        self._evaluate_model("compatibility", model, X_train_scaled, y_train, X_test_scaled, y_test)
    
    def _train_success_model(self, X: np.ndarray, y: np.ndarray):
        """Başarı olasılığı modelini eğit - XGBoost ile iyileştirilmiş"""
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # XGBoost (başarı olasılığı için daha önemli - daha derin ağaç)
        model = XGBRegressor(
            n_estimators=250,
            max_depth=7,
            learning_rate=0.04,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=42,
            objective='reg:squarederror',
            n_jobs=-1,
            tree_method='hist',
            min_child_weight=3,  # Overfitting'i önlemek için
            gamma=0.1  # Regularization
        )
        model.fit(X_train_scaled, y_train)
        
        self.models['success'] = model
        self.scalers['success'] = scaler
        
        self._evaluate_model("success", model, X_train_scaled, y_train, X_test_scaled, y_test)
    
    def _train_preference_model(self, X: np.ndarray, y: np.ndarray):
        """Tercih modelini eğit - XGBoost ile iyileştirilmiş"""
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # XGBoost (tercih skorları için)
        model = XGBRegressor(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            objective='reg:squarederror',
            n_jobs=-1,
            tree_method='hist'
        )
        model.fit(X_train_scaled, y_train)
        
        self.models['preference'] = model
        self.scalers['preference'] = scaler
        
        self._evaluate_model("preference", model, X_train_scaled, y_train, X_test_scaled, y_test)
    
    def _predict_compatibility(self, features: np.ndarray) -> float:
        """Uyumluluk skorunu tahmin et"""
        if 'compatibility' not in self.models:
            return 0.5  # Default value
        
        features_scaled = self.scalers['compatibility'].transform(features)
        return self.models['compatibility'].predict(features_scaled)[0]
    
    def _predict_success_probability(self, features: np.ndarray) -> float:
        """Başarı olasılığını tahmin et"""
        if 'success' not in self.models:
            return 0.5
        
        features_scaled = self.scalers['success'].transform(features)
        return self.models['success'].predict(features_scaled)[0]
    
    def _predict_preference(self, features: np.ndarray) -> float:
        """Tercih skorunu tahmin et"""
        if 'preference' not in self.models:
            return 0.5
        
        features_scaled = self.scalers['preference'].transform(features)
        return self.models['preference'].predict(features_scaled)[0]
    
    def _generate_ml_reason(self, compatibility: float, success: float, preference: float) -> str:
        """ML destekli öneri sebebi oluştur"""
        reasons = []
        
        if success >= 0.8:
            reasons.append("Yüksek başarı olasılığı (ML tahmini)")
        elif success >= 0.6:
            reasons.append("Orta başarı olasılığı (ML tahmini)")
        else:
            reasons.append("Düşük başarı olasılığı (ML tahmini)")
        
        if compatibility >= 0.8:
            reasons.append("Yüksek uyumluluk (ML tahmini)")
        elif compatibility >= 0.6:
            reasons.append("Orta uyumluluk (ML tahmini)")
        
        if preference >= 0.8:
            reasons.append("Tercihlerinize uygun (ML tahmini)")
        elif preference >= 0.6:
            reasons.append("Kısmen tercihlerinize uygun (ML tahmini)")
        
        return ", ".join(reasons) if reasons else "ML destekli genel uyumluluk"
    
    def _fallback_recommendations(self, student_id: int, limit: int) -> List[Dict[str, Any]]:
        """ML modelleri yoksa kural tabanlı sisteme geri dön"""
        from services.recommendation_engine import RecommendationEngine
        rule_engine = RecommendationEngine(self.db)
        recommendations = rule_engine.generate_recommendations(student_id, limit)
        # Convert Pydantic models to dicts
        result = []
        for rec in recommendations:
            rec_dict = rec.model_dump() if hasattr(rec, 'model_dump') else rec.dict()
            # Ensure department is accessible as ORM object if needed
            if 'department' not in rec_dict or isinstance(rec_dict['department'], dict):
                # Get department ORM object
                dept = self.db.query(Department).filter(Department.id == rec.department_id).first()
                if dept:
                    rec_dict['department'] = dept
            result.append(rec_dict)
        return result
    
    def _save_models(self):
        """Modelleri kaydet"""
        os.makedirs(self.model_path, exist_ok=True)
        
        for name, model in self.models.items():
            joblib.dump(model, f"{self.model_path}{name}_model.pkl")
        
        for name, scaler in self.scalers.items():
            joblib.dump(scaler, f"{self.model_path}{name}_scaler.pkl")
    
    def _load_models(self):
        """Modelleri yükle"""
        try:
            for name in ['compatibility', 'success', 'preference']:
                model_path = f"{self.model_path}{name}_model.pkl"
                scaler_path = f"{self.model_path}{name}_scaler.pkl"
                
                if os.path.exists(model_path) and os.path.exists(scaler_path):
                    self.models[name] = joblib.load(model_path)
                    self.scalers[name] = joblib.load(scaler_path)
                    self.is_trained = True
            
            if self.is_trained:
                recommendation_logger.info("ML models loaded successfully")
        except Exception as e:
            recommendation_logger.warning("Failed to load ML models", error=str(e))
    
    def _encode_field_type(self, field_type: str) -> int:
        """Alan türünü encode et"""
        mapping = {'SAY': 0, 'EA': 1, 'SÖZ': 2, 'DİL': 3}
        return mapping.get(field_type, 0)
    
    def _encode_exam_type(self, exam_type: str) -> int:
        """Sınav türünü encode et"""
        mapping = {'TYT': 0, 'AYT': 1, 'TYT+AYT': 2}
        return mapping.get(exam_type, 2)
    
    def _encode_class_level(self, class_level: str) -> int:
        """Sınıf seviyesini encode et"""
        mapping = {'12': 0, 'mezun': 1}
        return mapping.get(class_level, 0)
    
    def _encode_university_type(self, uni_type: str) -> int:
        """Üniversite türünü encode et"""
        mapping = {'Devlet': 0, 'Vakıf': 1, 'Özel': 2}
        return mapping.get(uni_type, 0)
    
    def _encode_city(self, city: str) -> int:
        """Şehri encode et"""
        # Basit hash fonksiyonu
        return hash(city) % 1000
