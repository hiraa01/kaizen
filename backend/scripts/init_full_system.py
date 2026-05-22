"""
✅ KAPSAMLI SİSTEM BAŞLATMA SCRIPTİ

Bu script, boş bir PostgreSQL veritabanını sıfırdan kurar:
1. Tüm tabloları oluşturur (Schema Creation)
2. Excel verilerini import eder (University, Department)
3. Admin ve test kullanıcısı oluşturur (Seeding)
4. Sequence'leri düzeltir (ID sayaç senkronizasyonu)

KULLANIM:
    # Docker container içinde:
    docker exec -it osym_rehberi_backend python scripts/init_full_system.py
    
    # Veya local'de:
    python scripts/init_full_system.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# ✅ Path ayarları
sys.path.append('/app' if os.path.exists('/app') else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, inspect
from sqlalchemy.exc import IntegrityError, OperationalError
from database import engine, SessionLocal, Base, create_tables, apply_runtime_schema_patches
from models import User, Student, University, Department
from core.logging_config import api_logger

# ✅ Renkli terminal çıktısı için ANSI kodları
class Colors:
    """Terminal renk kodları"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text: str):
    """Başlık yazdır"""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text.center(70)}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.ENDC}\n")

def print_success(text: str):
    """Başarı mesajı"""
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")

def print_warning(text: str):
    """Uyarı mesajı"""
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")

def print_error(text: str):
    """Hata mesajı"""
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")

def print_info(text: str):
    """Bilgi mesajı"""
    print(f"{Colors.OKCYAN}ℹ️  {text}{Colors.ENDC}")

def print_section(text: str):
    """Bölüm başlığı"""
    print(f"\n{Colors.BOLD}{Colors.OKBLUE}{'─' * 70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.OKBLUE}{text}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.OKBLUE}{'─' * 70}{Colors.ENDC}\n")


# ============================================================================
# 1. TABLO OLUŞTURMA (Schema Creation)
# ============================================================================

def create_all_tables() -> bool:
    """
    ✅ Tüm veritabanı tablolarını oluşturur
    
    Returns:
        bool: Başarılı ise True
    """
    print_section("1️⃣  TABLO OLUŞTURMA (Schema Creation)")
    
    try:
        print_info("Modeller import ediliyor...")
        
        # ✅ CRITICAL: Tüm modelleri import et (Base.metadata'ya kayıt için)
        # database.py'de zaten import edilmiş olmalı, ama emin olmak için tekrar import edelim
        try:
            from models import (
                User, Student, ExamAttempt,
                University, Department, DepartmentYearlyStats, Recommendation,
                Preference, Swipe,
                ForumPost, ForumComment,
                YokUniversity, YokProgram, YokCity, ScoreCalculation
            )
            # ✅ Opsiyonel modeller
            try:
                from models import AgendaItem, StudySession, ChatMessage  # type: ignore
                print_success("AgendaItem, StudySession, ChatMessage modelleri bulundu")
            except ImportError:
                print_warning("AgendaItem, StudySession, ChatMessage modelleri bulunamadı (opsiyonel)")
            
            print_success("Tüm modeller başarıyla import edildi")
        except ImportError as e:
            print_error(f"Model import hatası: {e}")
            import traceback
            print_error(traceback.format_exc())
            return False
        
        print_info("Veritabanı tabloları oluşturuluyor...")
        print_info("(Bu işlem mevcut tabloları değiştirmez, sadece eksik olanları oluşturur)")
        
        # ✅ database.py'deki create_tables fonksiyonunu kullan (retry logic ile)
        success = create_tables(max_retries=5, retry_delay=3)
        
        if success:
            # ✅ Oluşturulan tabloları kontrol et
            inspector = inspect(engine)
            created_tables = inspector.get_table_names()
            
            print_success(f"Tablolar başarıyla oluşturuldu! ({len(created_tables)} tablo)")
            print_info(f"Oluşturulan tablolar: {', '.join(sorted(created_tables))}")
            return True
        else:
            print_error("Tablo oluşturma başarısız!")
            return False
            
    except Exception as e:
        print_error(f"CRITICAL: Tablo oluşturma hatası: {e}")
        import traceback
        print_error(traceback.format_exc())
        return False


# ============================================================================
# 2. EXCEL VERİLERİNİ AKTARMA (Import)
# ============================================================================

def import_excel_data() -> Dict[str, int]:
    """
    ✅ Excel dosyalarından üniversite ve bölüm verilerini import eder
    
    Returns:
        dict: {"universities": count, "departments": count, "yearly_stats": count}
    """
    print_section("2️⃣  EXCEL VERİLERİNİ AKTARMA (Import)")
    
    # ✅ import_osym_excel.py script'ini çağır
    try:
        # Script'i import et
        import importlib.util
        script_path = Path(__file__).parent / "import_osym_excel.py"
        
        if not script_path.exists():
            print_warning(f"Excel import script'i bulunamadı: {script_path}")
            print_info("Excel import atlanıyor...")
            return {"universities": 0, "departments": 0, "yearly_stats": 0}
        
        print_info(f"Excel import script'i bulundu: {script_path.name}")
        print_info("Excel dosyaları aranıyor...")
        
        # ✅ import_osym_excel.py'nin main fonksiyonunu çağır
        spec = importlib.util.spec_from_file_location("import_osym_excel", script_path)
        if spec is None or spec.loader is None:
            print_error("Excel import script'i yüklenemedi (spec veya loader None)")
            return {"universities": 0, "departments": 0, "yearly_stats": 0}
        
        import_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(import_module)
        
        # ✅ Script'in main fonksiyonunu çağır
        if hasattr(import_module, 'main'):
            print_info("Excel import başlatılıyor...")
            print_warning("NOT: Bu işlem birkaç dakika sürebilir (binlerce kayıt)")
            
            # ✅ Script'i çalıştır (main fonksiyonu import işlemini yapar)
            try:
                import_module.main()
                print_success("Excel import tamamlandı!")
                
                # ✅ İstatistikleri al
                db = SessionLocal()
                try:
                    uni_count = db.query(University).count()
                    dept_count = db.query(Department).count()
                    
                    print_success(f"Import sonrası: {uni_count} üniversite, {dept_count} bölüm")
                    return {"universities": uni_count, "departments": dept_count, "yearly_stats": 0}
                finally:
                    db.close()
                    
            except Exception as import_error:
                print_error(f"Excel import hatası: {import_error}")
                import traceback
                print_error(traceback.format_exc())
                print_warning("Excel import atlanıyor, devam ediliyor...")
                return {"universities": 0, "departments": 0, "yearly_stats": 0}
        else:
            print_warning("Excel import script'inde 'main' fonksiyonu bulunamadı")
            print_info("Excel import atlanıyor...")
            return {"universities": 0, "departments": 0, "yearly_stats": 0}
            
    except Exception as e:
        print_error(f"Excel import script yükleme hatası: {e}")
        import traceback
        print_error(traceback.format_exc())
        print_warning("Excel import atlanıyor, devam ediliyor...")
        return {"universities": 0, "departments": 0, "yearly_stats": 0}


# ============================================================================
# 3. ADMIN VE TEST KULLANICISI OLUŞTURMA (Seeding)
# ============================================================================

def create_admin_user(db) -> Optional[User]:
    """
    ✅ Admin kullanıcısı oluşturur
    
    Args:
        db: Database session
    
    Returns:
        Optional[User]: Oluşturulan admin kullanıcısı veya None
    """
    try:
        # ✅ Mevcut admin var mı kontrol et
        existing_admin = db.query(User).filter(
            User.email == "admin@osymrehberi.com"
        ).first()
        
        if existing_admin:
            print_warning(f"Admin kullanıcısı zaten mevcut (ID: {existing_admin.id})")
            return existing_admin
        
        # ✅ Yeni admin kullanıcısı oluştur
        admin_user = User(
            email="admin@osymrehberi.com",
            phone="5550000001",
            name="Admin Kullanıcı",
            is_active=True,
            is_onboarding_completed=True,
            is_initial_setup_completed=True
        )
        
        db.add(admin_user)
        db.flush()  # ID almak için
        
        # ✅ Admin için Student profili oluştur
        admin_student = Student(
            user_id=admin_user.id,
            name="Admin Kullanıcı",
            email="admin@osymrehberi.com",
            phone="5550000001",
            class_level="mezun",
            exam_type="TYT+AYT",
            field_type="SAY",
            tyt_total_score=0.0,
            ayt_total_score=0.0,
            total_score=0.0
        )
        db.add(admin_student)
        db.commit()
        
        print_success(f"Admin kullanıcısı oluşturuldu (ID: {admin_user.id})")
        print_info("Email: admin@osymrehberi.com")
        print_info("NOT: Şifre sistemi şu an aktif değil, email/phone ile giriş yapılabilir")
        
        return admin_user
        
    except IntegrityError as e:
        db.rollback()
        print_warning(f"Admin kullanıcısı zaten mevcut olabilir: {e}")
        # Mevcut admin'i döndür
        existing_admin = db.query(User).filter(
            User.email == "admin@osymrehberi.com"
        ).first()
        return existing_admin
    except Exception as e:
        db.rollback()
        print_error(f"Admin kullanıcısı oluşturma hatası: {e}")
        import traceback
        print_error(traceback.format_exc())
        return None


def create_test_student(db) -> Optional[Student]:
    """
    ✅ Test öğrencisi oluşturur
    
    Args:
        db: Database session
    
    Returns:
        Optional[Student]: Oluşturulan test öğrencisi veya None
    """
    try:
        # ✅ Mevcut test öğrencisi var mı kontrol et
        existing_test = db.query(User).filter(
            User.email == "test@osymrehberi.com"
        ).first()
        
        if existing_test:
            print_warning(f"Test kullanıcısı zaten mevcut (ID: {existing_test.id})")
            student = db.query(Student).filter(Student.user_id == existing_test.id).first()
            return student
        
        # ✅ Test kullanıcısı oluştur
        test_user = User(
            email="test@osymrehberi.com",
            phone="5550000002",
            name="Test Öğrenci",
            is_active=True,
            is_onboarding_completed=True,
            is_initial_setup_completed=True
        )
        
        db.add(test_user)
        db.flush()  # ID almak için
        
        # ✅ Test öğrencisi profili oluştur
        test_student = Student(
            user_id=test_user.id,
            name="Test Öğrenci",
            email="test@osymrehberi.com",
            phone="5550000002",
            class_level="12",
            exam_type="TYT+AYT",
            field_type="SAY",
            tyt_turkish_net=15.0,
            tyt_math_net=20.0,
            tyt_social_net=10.0,
            tyt_science_net=18.0,
            ayt_math_net=25.0,
            ayt_physics_net=20.0,
            ayt_chemistry_net=18.0,
            ayt_biology_net=15.0,
            tyt_total_score=63.0,
            ayt_total_score=78.0,
            total_score=141.0,
            preferred_cities='["İstanbul", "Ankara"]',
            preferred_university_types='["devlet"]',
            scholarship_preference=True
        )
        
        db.add(test_student)
        db.commit()
        
        print_success(f"Test öğrencisi oluşturuldu (ID: {test_student.id})")
        print_info("Email: test@osymrehberi.com")
        
        return test_student
        
    except IntegrityError as e:
        db.rollback()
        print_warning(f"Test öğrencisi zaten mevcut olabilir: {e}")
        # Mevcut test öğrencisini döndür
        existing_test = db.query(User).filter(
            User.email == "test@osymrehberi.com"
        ).first()
        if existing_test:
            student = db.query(Student).filter(Student.user_id == existing_test.id).first()
            return student
        return None
    except Exception as e:
        db.rollback()
        print_error(f"Test öğrencisi oluşturma hatası: {e}")
        import traceback
        print_error(traceback.format_exc())
        return None


def create_seed_users() -> Dict[str, bool]:
    """
    ✅ Admin ve test kullanıcılarını oluşturur
    
    Returns:
        dict: {"admin": success, "test": success}
    """
    print_section("3️⃣  ADMIN VE TEST KULLANICISI OLUŞTURMA (Seeding)")
    
    db = SessionLocal()
    results = {"admin": False, "test": False}
    
    try:
        # ✅ Admin kullanıcısı
        print_info("Admin kullanıcısı oluşturuluyor...")
        admin_user = create_admin_user(db)
        results["admin"] = admin_user is not None
        
        # ✅ Test öğrencisi
        print_info("Test öğrencisi oluşturuluyor...")
        test_student = create_test_student(db)
        results["test"] = test_student is not None
        
        return results
        
    except Exception as e:
        print_error(f"CRITICAL: Kullanıcı oluşturma hatası: {e}")
        import traceback
        print_error(traceback.format_exc())
        return results
    finally:
        db.close()


# ============================================================================
# 4. SEQUENCE DÜZELTME (ID Sayaç Senkronizasyonu)
# ============================================================================

def get_all_tables_with_sequences() -> List[Tuple[str, str]]:
    """
    ✅ Tüm tabloları ve ID kolonlarını bulur (public şeması dahil)
    
    Returns:
        list: [(table_name, id_column_name), ...]
    """
    inspector = inspect(engine)
    
    # ✅ PostgreSQL'de tablolar genelde 'public' şemasında
    # Hem şema belirtmeden hem de 'public' şemasından tabloları al
    try:
        # Önce public şemasından tabloları al
        tables = inspector.get_table_names(schema='public')
    except Exception:
        # Şema belirtmeden dene
        try:
            tables = inspector.get_table_names()
        except Exception as e:
            print_error(f"Tablo listesi alınamadı: {e}")
            return []
    
    # Eğer boşsa, şema belirtmeden tekrar dene
    if not tables:
        try:
            tables = inspector.get_table_names()
        except Exception as e:
            print_error(f"Tablo listesi alınamadı (şema belirtmeden): {e}")
            return []
    
    tables_with_ids = []
    
    for table_name in tables:
        try:
            # ✅ Şema belirtmeden veya 'public' şemasından kolonları al
            try:
                columns = inspector.get_columns(table_name, schema='public')
            except Exception:
                columns = inspector.get_columns(table_name)
            
            # ID kolonunu bul (primary key ve integer olan)
            for col in columns:
                if col.get('primary_key') and 'int' in str(col.get('type')).lower():
                    tables_with_ids.append((table_name, col['name']))
                    break
        except Exception as e:
            print_warning(f"Tablo {table_name} kontrol edilemedi: {e}")
            continue
    
    return tables_with_ids


def fix_sequence_for_table(table_name: str, id_column: str, db) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    ✅ Bir tablonun sequence'ini düzeltir (public şeması dahil)
    
    Returns:
        Tuple[bool, Optional[int], Optional[str]]: (başarılı mı, max_id, sequence_name)
    """
    try:
        # ✅ Mevcut maksimum ID'yi bul (public şeması dahil)
        # PostgreSQL'de tablolar genelde 'public' şemasında
        max_id_query = text(f'SELECT COALESCE(MAX("{id_column}"), 0) FROM public."{table_name}"')
        try:
            result = db.execute(max_id_query)
            max_id = result.scalar() or 0
        except Exception:
            # Şema belirtmeden dene
            max_id_query = text(f'SELECT COALESCE(MAX("{id_column}"), 0) FROM "{table_name}"')
            result = db.execute(max_id_query)
            max_id = result.scalar() or 0
        
        # ✅ Sequence adını bul (public şeması dahil)
        # pg_get_serial_sequence fonksiyonu şema adını da döndürür: 'public.table_id_seq'
        sequence_query = text("""
            SELECT pg_get_serial_sequence(:table_schema_table, :id_column)
        """)
        # Önce 'public.table_name' formatında dene
        table_schema_table = f'public."{table_name}"'
        result = db.execute(sequence_query, {"table_schema_table": table_schema_table, "id_column": id_column})
        sequence_name = result.scalar()
        
        # Eğer bulunamadıysa, sadece table_name ile dene
        if not sequence_name:
            table_schema_table = f'"{table_name}"'
            result = db.execute(sequence_query, {"table_schema_table": table_schema_table, "id_column": id_column})
            sequence_name = result.scalar()
        
        if not sequence_name:
            return False, max_id, None
        
        # ✅ Sequence'i maksimum ID + 1'e ayarla
        # setval fonksiyonu sequence adını (şema dahil) alır
        setval_query = text("SELECT setval(:sequence_name, :max_id, false)")
        db.execute(setval_query, {"sequence_name": sequence_name, "max_id": max_id})
        db.commit()
        
        return True, max_id, sequence_name
        
    except Exception as e:
        print_error(f"{table_name}.{id_column} sequence düzeltme hatası: {e}")
        db.rollback()
        return False, None, None


def fix_all_sequences() -> Dict[str, int]:
    """
    ✅ Tüm tabloların sequence'lerini düzeltir
    
    Returns:
        dict: {"fixed": count, "failed": count, "skipped": count}
    """
    print_section("4️⃣  SEQUENCE DÜZELTME (ID Sayaç Senkronizasyonu)")
    
    db = SessionLocal()
    stats = {"fixed": 0, "failed": 0, "skipped": 0}
    
    try:
        # ✅ Tüm tabloları ve ID kolonlarını bul
        tables_with_ids = get_all_tables_with_sequences()
        
        if not tables_with_ids:
            print_warning("Hiç tablo bulunamadı!")
            return stats
        
        print_info(f"{len(tables_with_ids)} tablo bulundu\n")
        
        # ✅ Her tablo için sequence'i düzelt
        for table_name, id_column in tables_with_ids:
            print(f"🔧 {table_name}.{id_column} düzeltiliyor...", end=" ")
            
            success, max_id, sequence_name = fix_sequence_for_table(table_name, id_column, db)
            
            if success and sequence_name is not None and max_id is not None:
                print_success(f"Sequence '{sequence_name}' → {max_id + 1} (max_id={max_id})")
                stats["fixed"] += 1
            elif sequence_name is None:
                print_warning(f"Sequence bulunamadı (IDENTITY kullanılıyor olabilir, max_id={max_id})")
                stats["skipped"] += 1
            else:
                print_error(f"Düzeltme başarısız")
                stats["failed"] += 1
        
        print(f"\n{Colors.BOLD}📊 Özet:{Colors.ENDC}")
        print_success(f"Başarılı: {stats['fixed']}")
        if stats["skipped"] > 0:
            print_warning(f"Atlandı: {stats['skipped']}")
        if stats["failed"] > 0:
            print_error(f"Başarısız: {stats['failed']}")
        
        return stats
        
    except Exception as e:
        print_error(f"CRITICAL: Sequence düzeltme hatası: {e}")
        import traceback
        print_error(traceback.format_exc())
        return stats
    finally:
        db.close()


# ============================================================================
# ANA FONKSİYON
# ============================================================================

def main():
    """✅ Ana fonksiyon - Tüm initialization adımlarını çalıştırır"""
    print_header("KAPSAMLI SİSTEM BAŞLATMA")
    print(f"{Colors.OKCYAN}🕐 Başlangıç Zamanı: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.ENDC}\n")
    
    try:
        # ✅ 1. Tablo Oluşturma
        if not create_all_tables():
            print_error("Tablo oluşturma başarısız! Script durduruluyor.")
            return 1

        print_info("Runtime schema patches (yeni kolonlar) uygulanıyor...")
        try:
            apply_runtime_schema_patches()
            print_success("Schema patch'leri uygulandı (ör. departments.is_vocational)")
        except Exception as patch_err:
            print_warning(f"Schema patch atlandı veya hata: {patch_err}")

        # ✅ 2. Excel Verilerini Aktarma
        import_stats = import_excel_data()
        
        # ✅ 3. Admin ve Test Kullanıcısı Oluşturma
        seed_results = create_seed_users()
        
        # ✅ 4. Sequence Düzeltme
        sequence_stats = fix_all_sequences()
        
        # ✅ ÖZET RAPOR
        print_header("📋 ÖZET RAPOR")
        
        print(f"{Colors.BOLD}Tablo Oluşturma:{Colors.ENDC}")
        inspector = inspect(engine)
        table_count = len(inspector.get_table_names())
        print_success(f"{table_count} tablo oluşturuldu")
        
        print(f"\n{Colors.BOLD}Excel Import:{Colors.ENDC}")
        print_success(f"Üniversite: {import_stats['universities']}")
        print_success(f"Bölüm: {import_stats['departments']}")
        if import_stats['yearly_stats'] > 0:
            print_success(f"Yıllık İstatistik: {import_stats['yearly_stats']}")
        
        print(f"\n{Colors.BOLD}Kullanıcı Oluşturma:{Colors.ENDC}")
        if seed_results["admin"]:
            print_success("Admin kullanıcısı: admin@osymrehberi.com")
        else:
            print_error("Admin kullanıcısı oluşturulamadı")
        
        if seed_results["test"]:
            print_success("Test öğrencisi: test@osymrehberi.com")
        else:
            print_error("Test öğrencisi oluşturulamadı")
        
        print(f"\n{Colors.BOLD}Sequence Düzeltme:{Colors.ENDC}")
        print_success(f"Başarılı: {sequence_stats['fixed']}")
        if sequence_stats["skipped"] > 0:
            print_warning(f"Atlandı: {sequence_stats['skipped']}")
        if sequence_stats["failed"] > 0:
            print_error(f"Başarısız: {sequence_stats['failed']}")
        
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}✅ SİSTEM BAŞLATMA TAMAMLANDI!{Colors.ENDC}")
        print(f"{Colors.OKCYAN}🕐 Bitiş Zamanı: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.ENDC}\n")
        
        print(f"{Colors.BOLD}📝 GİRİŞ BİLGİLERİ:{Colors.ENDC}")
        print(f"{Colors.OKGREEN}Admin Email: admin@osymrehberi.com{Colors.ENDC}")
        print(f"{Colors.OKGREEN}Test Email: test@osymrehberi.com{Colors.ENDC}")
        print(f"{Colors.WARNING}NOT: Şifre sistemi şu an aktif değil, email/phone ile giriş yapılabilir{Colors.ENDC}\n")
        
        return 0
        
    except Exception as e:
        print_error(f"CRITICAL: Script hatası: {e}")
        import traceback
        print_error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

