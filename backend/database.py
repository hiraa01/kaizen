from sqlalchemy import create_engine, MetaData, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import logging

# Logger setup
api_logger = logging.getLogger("api")

# ✅ CRITICAL: TÜM MODELLERİ BURADA IMPORT ET
# SQLAlchemy'nin Base.metadata.create_all() çalışması için
# modellerin Base'e kayıt olması gerekiyor. Bu import'lar
# Base tanımlandıktan SONRA ama create_tables() çağrılmadan ÖNCE yapılmalı.
# 
# NOT: Import'ları try-except içine alarak eksik modellerin
# uygulamayı çökertmesini engelliyoruz.

# Database URL - PostgreSQL for production, SQLite for development
# ✅ PostgreSQL'e geçiş yapıldı - performans için kritik
# Environment variable'dan al, yoksa PostgreSQL varsayılan değerlerini kullan
# ✅ CRITICAL: Host için birden fazla env variable kontrolü (POSTGRES_HOST, POSTGRES_SERVER, DB_HOST)
POSTGRES_USER = os.getenv("POSTGRES_USER", "osym_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "osym_password")
POSTGRES_DB = os.getenv("POSTGRES_DB", "osym_rehber")
# ✅ Host için alternatif env variable'lar: POSTGRES_HOST, POSTGRES_SERVER, DB_HOST
# ✅ CRITICAL: localhost kullanılmamalı, Docker servis adı ('db') kullanılmalı
POSTGRES_HOST = os.getenv("POSTGRES_HOST") or os.getenv("POSTGRES_SERVER") or os.getenv("DB_HOST") or "db"
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

# ✅ PostgreSQL connection string - psycopg2 driver (senkron)
# NOT: asyncpg kullanmıyoruz, senkron psycopg2 kullanıyoruz
# Eğer async kullanmak istersen: postgresql+asyncpg://...
# ✅ CRITICAL: Environment variable'dan al, yoksa varsayılan değerleri kullan
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

# ✅ CRITICAL: PostgreSQL URL formatını doğrula ve düzelt
# Docker Compose'dan gelen DATABASE_URL'de driver belirtilmemiş olabilir
if not DATABASE_URL.startswith(("postgresql://", "postgresql+psycopg2://", "postgresql+asyncpg://")):
    api_logger.warning(f"⚠️ DATABASE_URL PostgreSQL formatında değil: {DATABASE_URL[:30]}...")
    # Eğer sadece postgresql:// ile başlıyorsa, psycopg2 ekle
    if DATABASE_URL.startswith("postgresql://") and "+psycopg2" not in DATABASE_URL and "+asyncpg" not in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
        api_logger.info("✅ DATABASE_URL psycopg2 driver ile güncellendi")

# ✅ CRITICAL: localhost kontrolü - Docker içinde localhost kullanılmamalı
if "localhost" in DATABASE_URL or "127.0.0.1" in DATABASE_URL:
    api_logger.warning(f"⚠️ DATABASE_URL'de localhost kullanılıyor! Docker içinde servis adı kullanılmalı (örn: 'db')")
    api_logger.warning(f"⚠️ Mevcut DATABASE_URL: {DATABASE_URL[:50]}...")
    # Otomatik düzeltme (sadece uyarı, değiştirme)
    api_logger.info(f"💡 Docker Compose'da POSTGRES_HOST='db' kullanıldığından emin olun")

# ✅ CRITICAL: Host adını logla (debug için)
api_logger.info(f"📊 Database connection config: Host={POSTGRES_HOST}, DB={POSTGRES_DB}, Port={POSTGRES_PORT}")

# Create engine with connection pooling for better performance
# ✅ PostgreSQL'e geçiş yapıldı - SQLite artık kullanılmıyor
if DATABASE_URL.startswith("sqlite"):
    # SQLite fallback (sadece development için)
    engine = create_engine(
        DATABASE_URL,
        connect_args={
            "check_same_thread": False,
        },
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        """SQLite performans optimizasyonları"""
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA optimize")
        cursor.close()
else:
    # ✅ PostgreSQL için optimize edilmiş connection pool
    # ✅ CRITICAL: psycopg2 driver kullanıyoruz (senkron)
    try:
        engine = create_engine(
            DATABASE_URL,
            pool_size=10,        # ✅ Connection pool size (kullanıcı isteği: 10)
            max_overflow=20,      # Additional connections beyond pool_size
            pool_pre_ping=True,  # ✅ CRITICAL: Connection health check - kopmuş bağlantıları tespit eder
            pool_recycle=1800,   # Recycle connections after 30 minutes (PostgreSQL'in idle timeout'undan önce)
            pool_timeout=30,     # Wait time for connection from pool (seconds)
            echo=False,          # SQL query logging (production'da kapalı)
            # ✅ PostgreSQL özel optimizasyonlar
            connect_args={
                "connect_timeout": 20,  # Connection timeout (20 seconds)
                "application_name": "osym_rehberi_api",  # Connection identifier (pg_stat_activity'de görünür)
                "options": "-c statement_timeout=300000",  # 5 minutes query timeout (300000 ms)
                # ✅ PostgreSQL encoding ayarları
                "client_encoding": "UTF8",
            },
        )
        api_logger.info(f"✅ PostgreSQL engine created successfully (Host: {POSTGRES_HOST}, DB: {POSTGRES_DB})")
    except Exception as e:
        api_logger.error(f"❌ CRITICAL: PostgreSQL engine creation failed: {e}")
        api_logger.error(f"❌ DATABASE_URL: {DATABASE_URL[:50]}...")  # Şifreyi gösterme
        raise

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()

# Metadata for table creation
metadata = MetaData()

# ✅ IMPORT ALL MODELS (After Base is created, before create_tables is called)
# ✅ CRITICAL: models/__init__.py'den relative import kullanarak circular import'u önle
try:
    # models paketinden import et (relative import kullanıyor)
    from models import (  # noqa: F401
        User, Student, ExamAttempt,
        University, Department, DepartmentYearlyStats, Recommendation,
        Preference, Swipe,
        ForumPost, ForumComment,
        YokUniversity, YokProgram, YokCity, ScoreCalculation,
        AgendaItem, StudySession, ChatMessage,
    )

    api_logger.info("✅ All models imported successfully from models package")

except ImportError as e:
    api_logger.error(f"❌ CRITICAL: Failed to import models: {e}")
    api_logger.error("❌ Some models may not be registered with Base.metadata!")
    import traceback
    api_logger.error(f"❌ Traceback: {traceback.format_exc()}")
    # Uygulamayı çökertme, sadece log
    pass


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables(max_retries: int = 3, retry_delay: int = 2):
    """
    Create all tables in the database (Auto-Migration) with retry logic
    
    NOT: Modeller zaten dosyanın üstünde import edildi (Base.metadata'ya kayıt için).
    Bu fonksiyon sadece tabloları oluşturur.
    
    Args:
        max_retries: Maksimum deneme sayısı (varsayılan: 3)
        retry_delay: Her deneme arası bekleme süresi (saniye, varsayılan: 2)
    
    Returns:
        bool: Tablolar başarıyla oluşturuldu ise True, aksi halde False
    """
    import time
    
    for attempt in range(1, max_retries + 1):
        try:
            api_logger.info(f"🔄 Starting database table creation (Auto-Migration)... (Deneme {attempt}/{max_retries})")
            
            # ✅ Modeller zaten import edildi (dosyanın üstünde)
            # Sadece tabloları oluştur
            api_logger.info("🔨 Creating database tables from registered models...")
            
            # Base.metadata'da kayıtlı tüm modeller için tabloları oluştur
            Base.metadata.create_all(bind=engine)
            
            # Oluşturulan tabloları kontrol et
            from sqlalchemy import inspect
            inspector = inspect(engine)
            created_tables = inspector.get_table_names()
            
            api_logger.info(f"✅ Tablolar başarıyla oluşturuldu! ({len(created_tables)} tablo)")
            api_logger.info(f"📊 Oluşturulan tablolar: {', '.join(sorted(created_tables))}")
            
            # Kayıtlı modelleri kontrol et
            registered_tables = list(Base.metadata.tables.keys())
            api_logger.info(f"📋 Kayıtlı modeller: {len(registered_tables)} tablo metadata'da")
            
            # ✅ CRITICAL: PostgreSQL sequence'leri düzelt (SQLite'tan geçiş sonrası)
            if not DATABASE_URL.startswith("sqlite"):
                try:
                    api_logger.info("🔧 PostgreSQL sequence'leri düzeltiliyor...")
                    from sqlalchemy import text, inspect
                    inspector = inspect(engine)
                    tables = inspector.get_table_names()
                    
                    # ✅ Tüm tablolar için sequence'leri düzelt
                    with engine.connect() as conn:
                        for table_name in tables:
                            try:
                                # ID kolonunu bul
                                columns = inspector.get_columns(table_name)
                                id_column = None
                                for col in columns:
                                    if col.get('primary_key') and 'int' in str(col.get('type')).lower():
                                        id_column = col['name']
                                        break
                                
                                if not id_column:
                                    continue
                                
                                # Maksimum ID'yi bul
                                max_id_result = conn.execute(text(f"SELECT COALESCE(MAX({id_column}), 0) FROM {table_name}"))
                                max_id = max_id_result.scalar() or 0
                                
                                # Sequence adını bul ve düzelt
                                seq_result = conn.execute(text(f"SELECT pg_get_serial_sequence(:table, :col)"), {"table": table_name, "col": id_column})
                                sequence_name = seq_result.scalar()
                                
                                if sequence_name:
                                    conn.execute(text(f"SELECT setval(:seq, :max_id, false)"), {"seq": sequence_name, "max_id": max_id})
                                    conn.commit()
                                    api_logger.info(f"✅ {table_name}.{id_column}: Sequence → {max_id + 1}")
                            except Exception as seq_error:
                                # Sequence yoksa veya IDENTITY kullanılıyorsa normal (PostgreSQL 10+)
                                if "does not exist" not in str(seq_error).lower():
                                    api_logger.warning(f"⚠️ {table_name} sequence düzeltme hatası: {seq_error}")
                                continue
                    
                    api_logger.info("✅ Sequence'ler düzeltildi!")
                except Exception as seq_fix_error:
                    api_logger.warning(f"⚠️ Sequence düzeltme sırasında hata (non-critical): {seq_fix_error}")
            
            return True
            
        except Exception as e:
            if attempt < max_retries:
                api_logger.warning(f"⚠️ Tablo oluşturma hatası (Deneme {attempt}/{max_retries}): {str(e)}")
                api_logger.info(f"⏳ {retry_delay} saniye bekleniyor...")
                time.sleep(retry_delay)
            else:
                api_logger.error(f"❌ TABLO OLUŞTURMA HATASI: {e}")
                import traceback
                api_logger.error(f"❌ Traceback: {traceback.format_exc()}")
                # Hata olsa bile uygulama çalışmaya devam etsin (sadece log)
                # Çünkü tablolar zaten var olabilir
                api_logger.warning("⚠️ Tablo oluşturma hatasına rağmen devam ediliyor (tablolar zaten var olabilir)")
                return False
    
    return False


def apply_runtime_schema_patches() -> None:
    """
    Lightweight ALTERs for existing PostgreSQL databases (create_all does not add columns).
    Safe to run repeatedly.
    """
    if DATABASE_URL.startswith("sqlite"):
        return
    from sqlalchemy import text

    statements = [
        (
            "ALTER TABLE departments ADD COLUMN IF NOT EXISTS is_vocational "
            "BOOLEAN NOT NULL DEFAULT false"
        ),
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS ml_update_frequency INTEGER NOT NULL DEFAULT 7",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS ml_last_trained_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS diploma_grade DOUBLE PRECISION",
        (
            "ALTER TABLE students ADD COLUMN IF NOT EXISTS student_status "
            "VARCHAR(30) NOT NULL DEFAULT 'student'"
        ),
    ]
    try:
        with engine.begin() as connection:
            for sql in statements:
                connection.execute(text(sql))
        api_logger.info("✅ Runtime schema patches applied (students ML + OBP columns)")
    except Exception as exc:
        api_logger.warning(f"⚠️ Runtime schema patch skipped or failed: {exc}")
