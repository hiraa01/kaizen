"""
YKS Puan Hesaplama Servisi
ÖSYM resmi katsayılarına göre TYT ve AYT puan hesaplaması + OBP desteği
"""
from typing import Any, Dict, Optional, Tuple


class ScoreCalculator:
    """YKS 2025 Puan Hesaplama - OBP Desteğiyle"""
    
    # ✅ OBP KATSAYILARI (ÖSYM Standartları)
    OBP_MULTIPLIERS = {
        'student': 0.6,           # 12. Sınıf veya Lise Öğrencisi - Tam OBP
        'graduated': 0.6,         # Mezun - Tam OBP
        'placement_broken': 0.3,  # Yerleşti / OBP Kırık - Yarıya Düşer
        'no_obp': 0.0            # OBP Hesaplamaya Katılmasın
    }
    
    # TYT Katsayıları (Sadece TYT'ye girenler için - 2 yıllık)
    TYT_ONLY_COEFFICIENTS = {
        'turkish': 3.3,
        'math': 3.3,
        'science': 3.4,
        'social': 3.4,
    }
    
    # TYT Katsayıları (4 yıllık için - AYT ile birlikte)
    TYT_FOR_AYT_COEFFICIENTS = {
        'turkish': 1.32,
        'math': 1.32,
        'science': 1.36,
        'social': 1.36,
    }
    
    # AYT Katsayıları - Sayısal (MF)
    AYT_SAY_COEFFICIENTS = {
        'math': 3.0,
        'physics': 2.85,
        'chemistry': 3.07,
        'biology': 3.07,
    }
    
    # AYT Katsayıları - Eşit Ağırlık (TM)
    AYT_EA_COEFFICIENTS = {
        'math': 3.0,
        'literature': 3.0,
        'history1': 2.8,
        'geography1': 3.33,
    }
    
    # AYT Katsayıları - Sözel (TS)
    AYT_SOZ_COEFFICIENTS = {
        'literature': 3.0,
        'history1': 2.8,
        'geography1': 3.33,
        'history2': 2.91,
        'geography2': 2.91,
        'philosophy': 3.0,
        'religion': 3.33,  # Din Kültürü
    }
    
    # AYT Katsayıları - Yabancı Dil
    AYT_DIL_COEFFICIENTS = {
        'language': 3.0,
    }
    
    BASE_SCORE = 100.0  # Taban puan
    MAX_SCORE = 560.0   # Maksimum puan
    
    @classmethod
    def calculate_tyt_score(
        cls,
        turkish_net: float,
        math_net: float,
        science_net: float,
        social_net: float,
        with_ayt: bool = True
    ) -> float:
        """
        TYT puanını hesaplar
        
        Args:
            turkish_net: Türkçe net sayısı
            math_net: Matematik net sayısı
            science_net: Fen net sayısı
            social_net: Sosyal net sayısı
            with_ayt: AYT'ye girecekse True (4 yıllık), sadece TYT'ye girecekse False (2 yıllık)
        
        Returns:
            TYT puanı (100-560 arası)
        """
        coefficients = cls.TYT_FOR_AYT_COEFFICIENTS if with_ayt else cls.TYT_ONLY_COEFFICIENTS
        
        tyt_raw_score = (
            turkish_net * coefficients['turkish'] +
            math_net * coefficients['math'] +
            science_net * coefficients['science'] +
            social_net * coefficients['social']
        )
        
        # Taban puan ekle
        tyt_score = cls.BASE_SCORE + tyt_raw_score
        
        # Limit kontrolü
        return min(max(tyt_score, cls.BASE_SCORE), cls.MAX_SCORE)
    
    @classmethod
    def calculate_ayt_score(
        cls,
        field_type: str,
        tyt_turkish_net: float,
        tyt_math_net: float,
        tyt_science_net: float,
        tyt_social_net: float,
        **ayt_nets
    ) -> float:
        """
        AYT puanını hesaplar (TYT katsayıları dahil)
        
        Args:
            field_type: Alan türü ('SAY', 'EA', 'SÖZ', 'DİL')
            tyt_turkish_net, tyt_math_net, tyt_science_net, tyt_social_net: TYT netleri
            **ayt_nets: AYT netleri (math_net, physics_net, chemistry_net, vb.)
        
        Returns:
            AYT puanı (100-560 arası)
        """
        field_type = field_type.upper()
        
        # TYT kısmı (AYT katsayılarıyla)
        tyt_part = (
            tyt_turkish_net * cls.TYT_FOR_AYT_COEFFICIENTS['turkish'] +
            tyt_math_net * cls.TYT_FOR_AYT_COEFFICIENTS['math'] +
            tyt_science_net * cls.TYT_FOR_AYT_COEFFICIENTS['science'] +
            tyt_social_net * cls.TYT_FOR_AYT_COEFFICIENTS['social']
        )
        
        # AYT kısmı (alan türüne göre)
        ayt_part = 0.0
        
        if field_type == 'SAY':  # Sayısal
            ayt_part = (
                ayt_nets.get('math_net', 0) * cls.AYT_SAY_COEFFICIENTS['math'] +
                ayt_nets.get('physics_net', 0) * cls.AYT_SAY_COEFFICIENTS['physics'] +
                ayt_nets.get('chemistry_net', 0) * cls.AYT_SAY_COEFFICIENTS['chemistry'] +
                ayt_nets.get('biology_net', 0) * cls.AYT_SAY_COEFFICIENTS['biology']
            )
        
        elif field_type == 'EA':  # Eşit Ağırlık
            ayt_part = (
                ayt_nets.get('math_net', 0) * cls.AYT_EA_COEFFICIENTS['math'] +
                ayt_nets.get('literature_net', 0) * cls.AYT_EA_COEFFICIENTS['literature'] +
                ayt_nets.get('history1_net', 0) * cls.AYT_EA_COEFFICIENTS['history1'] +
                ayt_nets.get('geography1_net', 0) * cls.AYT_EA_COEFFICIENTS['geography1']
            )
        
        elif field_type in ['SOZ', 'SÖZ']:  # Sözel
            ayt_part = (
                ayt_nets.get('literature_net', 0) * cls.AYT_SOZ_COEFFICIENTS['literature'] +
                ayt_nets.get('history1_net', 0) * cls.AYT_SOZ_COEFFICIENTS['history1'] +
                ayt_nets.get('geography1_net', 0) * cls.AYT_SOZ_COEFFICIENTS['geography1'] +
                ayt_nets.get('history2_net', 0) * cls.AYT_SOZ_COEFFICIENTS['history2'] +
                ayt_nets.get('geography2_net', 0) * cls.AYT_SOZ_COEFFICIENTS['geography2'] +
                ayt_nets.get('philosophy_net', 0) * cls.AYT_SOZ_COEFFICIENTS['philosophy'] +
                ayt_nets.get('religion_net', 0) * cls.AYT_SOZ_COEFFICIENTS.get('religion', 0)
            )
        
        elif field_type in ['DIL', 'DİL']:  # Yabancı Dil
            ayt_part = (
                ayt_nets.get('language_net', 0) * cls.AYT_DIL_COEFFICIENTS['language']
            )
        
        # Toplam AYT puanı
        ayt_score = cls.BASE_SCORE + tyt_part + ayt_part
        
        # Limit kontrolü
        return min(max(ayt_score, cls.BASE_SCORE), cls.MAX_SCORE)
    
    @classmethod
    def calculate_total_score_with_obp(
        cls,
        tyt_score: float,
        ayt_score: float,
        obp_score: Optional[float] = None
    ) -> float:
        """
        OBP ile toplam puan hesaplar
        
        Args:
            tyt_score: TYT puanı
            ayt_score: AYT puanı
            obp_score: OBP (Okul Başarı Puanı) - Opsiyonel
        
        Returns:
            Toplam puan (TYT + AYT + OBP)
        """
        # NOT: Kullanıcı "TYT ve AYT puanını toplamamalısın" dedi
        # Ama gerçekte YKS sistemi toplayarak hesaplıyor
        # Burada sadece OBP ekleniyor, TYT/AYT zaten ayrı tutulacak
        total = ayt_score  # AYT puanı zaten TYT'yi içeriyor
        
        if obp_score:
            total += obp_score
        
        return min(total, cls.MAX_SCORE)
    
    @classmethod
    def _parse_diploma_and_status(cls, attempt_data: Dict) -> Tuple[Optional[float], str]:
        raw_dg = attempt_data.get('diploma_grade')
        diploma_grade: Optional[float] = None
        if raw_dg is not None:
            try:
                diploma_grade = float(raw_dg)
            except (TypeError, ValueError):
                diploma_grade = None
        status = attempt_data.get('student_status') or 'student'
        if status not in cls.OBP_MULTIPLIERS:
            status = 'student'
        return diploma_grade, status

    @classmethod
    def _branch_key_from_field_type(cls, field_type: Optional[str]) -> str:
        ft = (field_type or 'SAY').upper().replace('İ', 'I').replace('Ö', 'O')
        if ft == 'SAY':
            return 'say'
        if ft == 'EA':
            return 'ea'
        if ft in ('SÖZ', 'SOZ'):
            return 'soz'
        if ft in ('DİL', 'DIL'):
            return 'dil'
        return 'say'

    @classmethod
    def calculate_all_scores(cls, attempt_data: Dict) -> Dict[str, Any]:
        """
        Deneme / öğrenci verisinden yerleştirme puanlarını hesaplar (ham + OBP).

        Yerleştirme puanı = ham puan + (diploma notu × durum çarpanı).
        """
        diploma_grade, student_status = cls._parse_diploma_and_status(attempt_data)
        detailed = cls.calculate_all_scores_detailed(
            attempt_data,
            diploma_grade=diploma_grade,
            student_status=student_status,
        )
        exam_type = (attempt_data.get('exam_type') or 'TYT+AYT').upper().replace(' ', '')
        rank = 0
        percentile = 0.0

        if exam_type == 'TYT':
            tyt_block = detailed['tyt']
            return {
                'tyt_total_score': round(tyt_block['placement_score'], 4),
                'ayt_total_score': 0.0,
                'total_score': round(tyt_block['placement_score'], 4),
                'obp_score': round(tyt_block['obp_added'], 4),
                'rank': rank,
                'percentile': percentile,
            }

        branch = cls._branch_key_from_field_type(attempt_data.get('field_type'))
        tyt_block = detailed['tyt']
        branch_block = detailed[branch]
        return {
            'tyt_total_score': round(tyt_block['placement_score'], 4),
            'ayt_total_score': round(branch_block['placement_score'], 4),
            'total_score': round(branch_block['placement_score'], 4),
            'obp_score': round(branch_block['obp_added'], 4),
            'rank': rank,
            'percentile': percentile,
        }
    
    @classmethod
    def calculate_goal_proximity(
        cls,
        student_tyt_score: float,
        student_ayt_score: float,
        target_tyt_score: float,
        target_ayt_score: float
    ) -> Dict[str, float]:
        """
        Hedefe yakınlık hesaplar (TYT ve AYT AYRI karşılaştırılır)
        
        Args:
            student_tyt_score: Öğrencinin TYT puanı
            student_ayt_score: Öğrencinin AYT puanı
            target_tyt_score: Hedef bölümün TYT taban puanı
            target_ayt_score: Hedef bölümün AYT taban puanı
        
        Returns:
            {
                'tyt_proximity': TYT yakınlık yüzdesi (0-100),
                'ayt_proximity': AYT yakınlık yüzdesi (0-100),
                'overall_proximity': Genel yakınlık yüzdesi (0-100),
                'tyt_gap': TYT puan farkı,
                'ayt_gap': AYT puan farkı,
                'is_ready': Hedef için hazır mı?
            }
        """
        tyt_gap = target_tyt_score - student_tyt_score
        ayt_gap = target_ayt_score - student_ayt_score
        
        # Yakınlık yüzdesi (100% = hedef puanına ulaşmış veya aşmış)
        tyt_proximity = min(100.0, (student_tyt_score / target_tyt_score) * 100) if target_tyt_score > 0 else 100.0
        ayt_proximity = min(100.0, (student_ayt_score / target_ayt_score) * 100) if target_ayt_score > 0 else 100.0
        
        # Genel yakınlık (TYT ve AYT ortalaması)
        overall_proximity = (tyt_proximity + ayt_proximity) / 2.0
        
        # Hedefe hazır mı? (Her iki puan da hedefi geçmiş olmalı)
        is_ready = student_tyt_score >= target_tyt_score and student_ayt_score >= target_ayt_score
        
        return {
            'tyt_proximity': round(tyt_proximity, 2),
            'ayt_proximity': round(ayt_proximity, 2),
            'overall_proximity': round(overall_proximity, 2),
            'tyt_gap': round(tyt_gap, 2),
            'ayt_gap': round(ayt_gap, 2),
            'is_ready': is_ready
        }    
    @classmethod
    def calculate_placement_score(
        cls,
        raw_score: float,
        diploma_grade: Optional[float] = None,
        student_status: str = 'student'
    ) -> Dict[str, float]:
        """
        ✅ OBP ile Yerleştirme Puanı Hesapla
        
        ÖSYM Formülü:
        Yerleştirme Puanı = Ham Puan + (Diploma Notu * Durum Çarpanı)
        
        Args:
            raw_score: Ham puan (100 + netler)
            diploma_grade: Mezun notu (0-100), None'sa 0 kabul edilir
            student_status: 'student', 'graduated', 'placement_broken', 'no_obp'
        
        Returns:
            {
                'raw_score': 250.00,        # Ham puan
                'obp_multiplier': 0.6,      # Uygulanacak çarpan
                'obp_added': 48.00,         # Eklenen OBP miktarı
                'placement_score': 298.00   # Nihai yerleştirme puanı
            }
        """
        # OBP çarpanını al (default student)
        obp_multiplier = cls.OBP_MULTIPLIERS.get(student_status, 0.6)
        
        # Diploma notasını al ve validasyon yap
        if not diploma_grade or diploma_grade < 0 or diploma_grade > 100:
            diploma_grade = 0.0  # Geçersiz ise 0 al
        
        # OBP hesapla: Diploma Notu * Çarpan
        obp_added = round(diploma_grade * obp_multiplier, 2)
        
        # Yerleştirme puanı = Ham puan + OBP
        placement_score = round(raw_score + obp_added, 2)
        
        return {
            'raw_score': round(raw_score, 2),
            'obp_multiplier': obp_multiplier,
            'obp_added': obp_added,
            'placement_score': placement_score
        }
    
    @classmethod
    def calculate_all_scores_detailed(
        cls,
        student_data: Dict,
        diploma_grade: Optional[float] = None,
        student_status: str = 'student'
    ) -> Dict[str, Dict]:
        """
        ✅ TYT, SAY, EA, SÖZ, DİL puanlarını OBP'yle birlikte hesapla
        
        Args:
            student_data: {
                'field_type': 'SAY',
                'tyt_turkish_net': 40.5,
                'tyt_math_net': 35.0,
                ...
                'ayt_math_net': 30.0,
                ...
            }
            diploma_grade: Diploma notu (0-100)
            student_status: 'student', 'graduated', 'placement_broken', 'no_obp'
        
        Returns:
            {
                'tyt': {
                    'raw_score': 250.00,
                    'obp_added': 48.00,
                    'placement_score': 298.00
                },
                'say': { ... },
                'ea': { ... },
                'soz': { ... },
                'dil': { ... }
            }
        """
        result = {}
        
        # TYT ham puanı: önlisans / "sadece TYT" katsayıları (Tr 3.3, Mat 3.3, …)
        tyt_raw = cls.calculate_tyt_score(
            turkish_net=student_data.get('tyt_turkish_net', 0.0),
            math_net=student_data.get('tyt_math_net', 0.0),
            science_net=student_data.get('tyt_science_net', 0.0),
            social_net=student_data.get('tyt_social_net', 0.0),
            with_ayt=False,
        )
        
        # TYT + OBP
        result['tyt'] = cls.calculate_placement_score(
            tyt_raw, 
            diploma_grade=diploma_grade,
            student_status=student_status
        )
        
        # SAY (Sayısal) Puanı
        say_raw = cls.calculate_ayt_score(
            field_type='SAY',
            tyt_turkish_net=student_data.get('tyt_turkish_net', 0.0),
            tyt_math_net=student_data.get('tyt_math_net', 0.0),
            tyt_science_net=student_data.get('tyt_science_net', 0.0),
            tyt_social_net=student_data.get('tyt_social_net', 0.0),
            math_net=student_data.get('ayt_math_net', 0.0),
            physics_net=student_data.get('ayt_physics_net', 0.0),
            chemistry_net=student_data.get('ayt_chemistry_net', 0.0),
            biology_net=student_data.get('ayt_biology_net', 0.0)
        )
        result['say'] = cls.calculate_placement_score(
            say_raw,
            diploma_grade=diploma_grade,
            student_status=student_status
        )
        
        # EA (Eşit Ağırlık) Puanı
        ea_raw = cls.calculate_ayt_score(
            field_type='EA',
            tyt_turkish_net=student_data.get('tyt_turkish_net', 0.0),
            tyt_math_net=student_data.get('tyt_math_net', 0.0),
            tyt_science_net=student_data.get('tyt_science_net', 0.0),
            tyt_social_net=student_data.get('tyt_social_net', 0.0),
            math_net=student_data.get('ayt_math_net', 0.0),
            literature_net=student_data.get('ayt_literature_net', 0.0),
            history1_net=student_data.get('ayt_history1_net', 0.0),
            geography1_net=student_data.get('ayt_geography1_net', 0.0)
        )
        result['ea'] = cls.calculate_placement_score(
            ea_raw,
            diploma_grade=diploma_grade,
            student_status=student_status
        )
        
        # SÖZ (Sözel) Puanı
        soz_raw = cls.calculate_ayt_score(
            field_type='SÖZ',
            tyt_turkish_net=student_data.get('tyt_turkish_net', 0.0),
            tyt_math_net=student_data.get('tyt_math_net', 0.0),
            tyt_science_net=student_data.get('tyt_science_net', 0.0),
            tyt_social_net=student_data.get('tyt_social_net', 0.0),
            literature_net=student_data.get('ayt_literature_net', 0.0),
            history1_net=student_data.get('ayt_history1_net', 0.0),
            geography1_net=student_data.get('ayt_geography1_net', 0.0),
            history2_net=student_data.get('ayt_history2_net', 0.0),
            geography2_net=student_data.get('ayt_geography2_net', 0.0),
            philosophy_net=student_data.get('ayt_philosophy_net', 0.0),
            religion_net=student_data.get('ayt_religion_net', 0.0)
        )
        result['soz'] = cls.calculate_placement_score(
            soz_raw,
            diploma_grade=diploma_grade,
            student_status=student_status
        )
        
        # DİL (Dil) Puanı
        dil_raw = cls.calculate_ayt_score(
            field_type='DİL',
            tyt_turkish_net=student_data.get('tyt_turkish_net', 0.0),
            tyt_math_net=student_data.get('tyt_math_net', 0.0),
            tyt_science_net=student_data.get('tyt_science_net', 0.0),
            tyt_social_net=student_data.get('tyt_social_net', 0.0),
            language_net=student_data.get('ayt_foreign_language_net', 0.0)
        )
        result['dil'] = cls.calculate_placement_score(
            dil_raw,
            diploma_grade=diploma_grade,
            student_status=student_status
        )
        
        return result