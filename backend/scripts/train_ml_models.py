#!/usr/bin/env python3
"""
ML modellerini eğitmek için script
Bu script geçmiş verilerle modelleri eğitir ve kaydeder
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from database import get_db
from services.ml_recommendation_engine import MLRecommendationEngine
from models.student import Student
from models.university import Department, Recommendation
import json

def generate_training_data():
    """Eğitim verisi oluştur (gerçek veri yoksa simüle edilmiş)"""
    print("Eğitim verisi oluşturuluyor...")
    
    # Simüle edilmiş eğitim verisi
    training_data = []
    
    # Farklı öğrenci profilleri
    student_profiles = [
        {'total_score': 500, 'rank': 500, 'field_type': 'SAY', 'exam_type': 'TYT+AYT'},
        {'total_score': 450, 'rank': 1000, 'field_type': 'SAY', 'exam_type': 'TYT+AYT'},
        {'total_score': 400, 'rank': 2000, 'field_type': 'EA', 'exam_type': 'TYT+AYT'},
        {'total_score': 350, 'rank': 5000, 'field_type': 'SÖZ', 'exam_type': 'TYT+AYT'},
        {'total_score': 300, 'rank': 10000, 'field_type': 'DİL', 'exam_type': 'TYT+AYT'},
    ]
    
    # Farklı bölüm profilleri
    department_profiles = [
        {'min_score': 480, 'min_rank': 800, 'university_type': 'Devlet', 'city': 'İstanbul'},
        {'min_score': 450, 'min_rank': 1500, 'university_type': 'Devlet', 'city': 'Ankara'},
        {'min_score': 420, 'min_rank': 2500, 'university_type': 'Vakıf', 'city': 'İstanbul'},
        {'min_score': 380, 'min_rank': 5000, 'university_type': 'Devlet', 'city': 'İzmir'},
        {'min_score': 350, 'min_rank': 8000, 'university_type': 'Vakıf', 'city': 'Bursa'},
    ]
    
    # Her öğrenci-bölüm kombinasyonu için veri oluştur
    for student in student_profiles:
        for dept in department_profiles:
            # Uyumluluk skoru hesapla
            score_diff = student['total_score'] - dept['min_score']
            compatibility = max(0, min(1, 0.5 + (score_diff / 100) * 0.3))
            
            # Başarı olasılığı hesapla
            if score_diff > 50:
                success_prob = 0.9
            elif score_diff > 20:
                success_prob = 0.7
            elif score_diff > 0:
                success_prob = 0.5
            elif score_diff > -20:
                success_prob = 0.3
            else:
                success_prob = 0.1
            
            # Tercih skoru (rastgele + bazı kurallar)
            preference = np.random.uniform(0.3, 0.9)
            if student['field_type'] == 'SAY' and dept['university_type'] == 'Devlet':
                preference += 0.1
            if dept['city'] == 'İstanbul':
                preference += 0.05
            
            preference = min(1.0, preference)
            
            training_data.append({
                'total_score': student['total_score'],
                'rank': student['rank'],
                'percentile': 100 - (student['rank'] / 1000),
                'tyt_total_score': student['total_score'] * 0.6,
                'ayt_total_score': student['total_score'] * 0.4,
                'field_type_encoded': {'SAY': 0, 'EA': 1, 'SÖZ': 2, 'DİL': 3}[student['field_type']],
                'exam_type_encoded': {'TYT': 0, 'AYT': 1, 'TYT+AYT': 2}[student['exam_type']],
                'class_level_encoded': 0,  # 12. sınıf
                'min_score': dept['min_score'],
                'min_rank': dept['min_rank'],
                'quota': np.random.randint(50, 200),
                'tuition_fee': 0 if dept['university_type'] == 'Devlet' else np.random.randint(50000, 100000),
                'has_scholarship': dept['university_type'] == 'Vakıf',
                'university_type_encoded': {'Devlet': 0, 'Vakıf': 1, 'Özel': 2}[dept['university_type']],
                'city_encoded': hash(dept['city']) % 1000,
                'compatibility': compatibility,
                'success_probability': success_prob,
                'preference': preference,
            })
    
    print(f"{len(training_data)} eğitim verisi oluşturuldu")
    return training_data

def train_models():
    """ML modellerini eğit"""
    print("ML modelleri eğitiliyor...")
    
    # Veritabanı bağlantısı
    db = next(get_db())
    
    try:
        # ML engine oluştur
        ml_engine = MLRecommendationEngine(db)
        
        # Eğitim verisi oluştur
        training_data = generate_training_data()
        
        # Modelleri eğit
        ml_engine.train_models(training_data)
        
        print("✅ ML modelleri başarıyla eğitildi!")
        print(f"📊 Eğitim verisi: {len(training_data)} örnek")
        print("🎯 Modeller kaydedildi: models/ klasörü")

        # ✅ Gerçek regresyon metrikleri (RMSE/MAE/R2) - model.score() (sadece R2) yeterli değil
        if ml_engine.last_training_metrics:
            print("\n📐 Değerlendirme metrikleri (test seti):")
            for model_name, m in ml_engine.last_training_metrics.items():
                print(
                    f"   {model_name}: RMSE={m['test_rmse']:.4f}  MAE={m['test_mae']:.4f}  "
                    f"R2={m['test_r2']:.4f}  (n_test={m['n_test']})"
                )
            print(
                "   ⚠️  Bu metrikler, eğitim verisi sentetik/kural tabanlı etiketlerle "
                "üretildiyse gerçek isabet oranını göstermez."
            )
        
        # Test önerisi oluştur (veritabanından ilk öğrenciyi bul)
        print("\n🧪 Test önerisi oluşturuluyor...")
        first_student = db.query(Student).first()
        
        if not first_student:
            print("⚠️  Veritabanında öğrenci bulunamadı - test atlandı")
            print("💡 Test için önce bir öğrenci profili oluşturun")
        else:
            print(f"📝 Test öğrencisi: {first_student.name} (ID: {first_student.id})")
            try:
                test_recommendations = ml_engine.generate_recommendations(first_student.id, limit=3)
                
                if not test_recommendations:
                    print("⚠️  Öneri oluşturulamadı (bölüm bulunamadı veya veri eksik)")
                else:
                    for i, rec in enumerate(test_recommendations, 1):
                        print(f"\n{i}. Öneri:")
                        print(f"   Bölüm: {rec['department'].name}")
                        print(f"   Uyumluluk: {rec['compatibility_score']:.2f}")
                        print(f"   Başarı Olasılığı: {rec['success_probability']:.2f}")
                        print(f"   Tercih Skoru: {rec['preference_score']:.2f}")
                        print(f"   Final Skor: {rec['final_score']:.2f}")
                        print(f"   Sebep: {rec['recommendation_reason']}")
            except Exception as test_error:
                print(f"⚠️  Test önerisi oluşturulurken hata: {test_error}")
                print("💡 Modeller eğitildi ancak test atlandı")
        
    except Exception as e:
        print(f"❌ Hata: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    train_models()
