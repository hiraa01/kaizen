from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import asyncio
from datetime import datetime

# ✅ CRITICAL: Import database first to ensure all models are registered
# database.py içinde tüm modeller zaten import ediliyor (Base.metadata'ya kayıt için)
from database import create_tables, get_db, Base, apply_runtime_schema_patches
from core.logging_config import api_logger

from routers import (
    students,
    universities,
    recommendations,
    ml_recommendations,
    auth,
    exam_attempts,
    coach_chat,
    preferences,
    discovery,
    chatbot,
    profile,
    forum,
    stats,
    agenda,
    study,
    targets,
    settings,
    ai_analysis,
    reports,
    admin_panel,
)


async def _wait_for_database(max_retries: int = 10, retry_delay: int = 5):
    """
    Veritabanı bağlantısını kontrol et ve hazır olana kadar bekle (Retry Logic - While Loop)
    
    ✅ CRITICAL: Bu fonksiyon asla exception fırlatmaz - sadece True/False döner
    Container'ın restart loop'a girmesini önlemek için tüm hatalar yakalanır.
    
    Args:
        max_retries: Maksimum deneme sayısı (varsayılan: 10)
        retry_delay: Her deneme arası bekleme süresi (saniye, varsayılan: 5)
    
    Returns:
        bool: Bağlantı başarılı ise True, aksi halde False
    """
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError
    from database import engine
    
    retries = max_retries
    
    while retries > 0:
        try:
            api_logger.info(f"🔄 Veritabanı bağlantısı deneniyor... ({max_retries - retries + 1}/{max_retries} deneme kaldı)")
            
            # Basit bir SQL sorgusu ile bağlantıyı test et
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                conn.commit()
            
            api_logger.info("✅ Veritabanı bağlantısı başarılı!")
            return True
            
        except OperationalError as e:
            # ✅ Veritabanı henüz hazır değil - normal durum
            retries -= 1
            if retries > 0:
                api_logger.warning(f"⚠️ Veritabanı henüz hazır değil ({retries} deneme kaldı): {str(e)}")
                api_logger.info(f"⏳ {retry_delay} saniye bekleniyor...")
                await asyncio.sleep(retry_delay)
            else:
                api_logger.error(f"❌ Veritabanı bağlantısı {max_retries} denemede başarısız oldu!")
                api_logger.error(f"❌ Son hata: {str(e)}")
                return False
        except Exception as e:
            # ✅ Beklenmeyen hatalar - logla ama devam et
            retries -= 1
            if retries > 0:
                api_logger.warning(f"⚠️ Veritabanı bağlantı hatası ({retries} deneme kaldı): {str(e)}")
                api_logger.info(f"⏳ {retry_delay} saniye bekleniyor...")
                await asyncio.sleep(retry_delay)
            else:
                api_logger.error(f"❌ Veritabanı bağlantısı {max_retries} denemede başarısız oldu!")
                api_logger.error(f"❌ Son hata: {str(e)}")
                return False
    
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    api_logger.info("=" * 60)
    api_logger.info("🚀 Starting kAIzen API...")
    api_logger.info("=" * 60)
    
    # ✅ CRITICAL: Tüm startup hatalarını yakala - uygulama çökmesin
    try:
        # ✅ 0. VERİTABANI BAĞLANTISINI BEKLE (Retry Logic - While Loop)
        api_logger.info("📋 Step 0: Waiting for database connection...")
        db_ready = await _wait_for_database(max_retries=10, retry_delay=5)  # 10 deneme, 5 saniye aralık
        
        if not db_ready:
            api_logger.error("❌ CRITICAL: Veritabanı bağlantısı kurulamadı!")
            api_logger.error("❌ Tüm denemeler başarısız oldu. Lütfen veritabanı servisini kontrol edin.")
            api_logger.warning("⚠️ Uygulama devam ediyor (logları kontrol edin). Bazı özellikler çalışmayabilir.")
            # ✅ Uygulamayı kapatma, sadece log bas (Konteyner çöküp durmasın)
            # raise RuntimeError("Database connection failed after multiple retries")  # Kaldırıldı
    except Exception as startup_error:
        # ✅ CRITICAL: Startup sırasında herhangi bir hata olsa bile uygulama çökmesin
        api_logger.error(f"🔥 STARTUP HATASI (Yakalandı - Uygulama devam ediyor): {str(startup_error)}")
        import traceback
        api_logger.error(f"🔥 Traceback: {traceback.format_exc()}")
        api_logger.warning("⚠️ Uygulama hata ile devam ediyor. Bazı özellikler çalışmayabilir.")
        db_ready = False
    
    # ✅ 1. VERİTABANI TABLOLARINI OLUŞTUR (Auto-Migration) - Sadece bağlantı başarılıysa
    if db_ready:
            api_logger.info("📋 Step 1: Creating database tables (Auto-Migration)...")
            try:
                tables_created = create_tables(max_retries=3, retry_delay=2)
                if tables_created:
                    api_logger.info("✅ Database tables ready!")
                else:
                    api_logger.warning("⚠️ Database table creation had issues, but continuing...")
            except Exception as e:
                # ✅ CRITICAL: Tablo oluşturma hatası uygulamayı çökertmesin
                api_logger.error(f"❌ TABLO OLUŞTURMA HATASI (Yakalandı): {e}")
                import traceback
                api_logger.error(f"❌ Traceback: {traceback.format_exc()}")
                api_logger.warning("⚠️ Uygulama devam ediyor (tablolar zaten var olabilir)")
            finally:
                apply_runtime_schema_patches()
    else:
        api_logger.warning("⚠️ Veritabanı bağlantısı olmadığı için tablo oluşturma atlandı.")

    # ✅ 2. Cache'i startup'ta yükle - statik veriler için (Sadece bağlantı başarılıysa)
    if db_ready:
        api_logger.info("📋 Step 2: Loading cache for static data...")
        try:
            db = next(get_db())
            try:
                # Cities cache
                # ✅ IMPORTANT: Cities list should be clean and deterministic.
                # DB-derived city names may include typos/encoding issues ("Bilinmiyor", foreign locations, etc.).
                # Frontend expects "81 il + KKTC" list for city preference selection.
                from models import Department
                from core.cache import set_cache
                from datetime import timedelta
                
                TURKISH_81_CITIES = [
                    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Aksaray", "Amasya", "Ankara", "Antalya",
                    "Ardahan", "Artvin", "Aydın", "Balıkesir", "Bartın", "Batman", "Bayburt", "Bilecik",
                    "Bingöl", "Bitlis", "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum",
                    "Denizli", "Diyarbakır", "Düzce", "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir",
                    "Gaziantep", "Giresun", "Gümüşhane", "Hakkari", "Hatay", "Iğdır", "Isparta", "İstanbul",
                    "İzmir", "Kahramanmaraş", "Karabük", "Karaman", "Kars", "Kastamonu", "Kayseri", "Kırıkkale",
                    "Kırklareli", "Kırşehir", "Kilis", "Kocaeli", "Konya", "Kütahya", "Malatya", "Manisa",
                    "Mardin", "Mersin", "Muğla", "Muş", "Nevşehir", "Niğde", "Ordu", "Osmaniye",
                    "Rize", "Sakarya", "Samsun", "Siirt", "Sinop", "Sivas", "Şanlıurfa", "Şırnak",
                    "Tekirdağ", "Tokat", "Trabzon", "Tunceli", "Uşak", "Van", "Yalova", "Yozgat", "Zonguldak"
                ]
                KKTC_CITIES = ["Lefkoşa", "Gazimağusa", "Girne", "Güzelyurt", "İskele"]
                
                def _normalize_city_name(text: str) -> str:
                    replacements = {
                        'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u',
                        'Ç': 'c', 'Ğ': 'g', 'İ': 'i', 'Ö': 'o', 'Ş': 's', 'Ü': 'u'
                    }
                    result = text.lower().strip()
                    for tr, en in replacements.items():
                        result = result.replace(tr, en)
                    return result
                
                def _turkish_sort_key(text: str) -> str:
                    return _normalize_city_name(text)
                
                merged = sorted(TURKISH_81_CITIES, key=_turkish_sort_key) + sorted(KKTC_CITIES, key=_turkish_sort_key)
                seen = set()
                cities = []
                for city in merged:
                    key = _normalize_city_name(city)
                    if key not in seen:
                        seen.add(key)
                        cities.append(city)
                
                set_cache("cities", cities, ttl=timedelta(hours=24))  # 24 saat cache
                api_logger.info(f"✅ Cached {len(cities)} cities (81 il + KKTC)")
                
                # Field types cache
                from sqlalchemy import distinct
                field_types_result = db.query(distinct(Department.field_type)).filter(Department.field_type.isnot(None)).all()
                field_types = [ft[0] for ft in field_types_result if ft[0]]
                set_cache("field_types", field_types, ttl=timedelta(hours=24))  # 24 saat cache
                api_logger.info(f"✅ Cached {len(field_types)} field types")
            finally:
                db.close()
        except Exception as e:
            # ✅ CRITICAL: Cache yükleme hatası uygulamayı çökertmesin
            api_logger.warning(f"⚠️ Cache loading failed (non-critical): {str(e)}")
    else:
        api_logger.warning("⚠️ Veritabanı bağlantısı olmadığı için cache yükleme atlandı.")
    
    # ✅ 3. APScheduler ile öğrenci bazlı ML eğitim pencerelerini yönet
    api_logger.info("📋 Step 3: Starting APScheduler (ML training due checks)...")
    try:
        from services.ml_training_scheduler import start_ml_training_scheduler

        start_ml_training_scheduler()
    except Exception as e:
        api_logger.error(f"⚠️ APScheduler başlatılamadı (non-critical): {str(e)}")

    api_logger.info("=" * 60)
    api_logger.info("✅ Application started successfully!")
    api_logger.info("=" * 60)

    log_all_routes()

    api_logger.info("=" * 60)
    api_logger.info("📋 REGISTERED API ROUTES:")
    api_logger.info("=" * 60)
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            methods = ", ".join(sorted(route.methods)) if route.methods else "N/A"
            api_logger.info(f"  {methods:20} {route.path}")
    api_logger.info("=" * 60)

    if db_ready:
        try:
            from sqlalchemy import inspect
            from database import engine

            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()
            api_logger.info(f"📊 Veritabanında mevcut tablolar: {len(existing_tables)} adet")
            api_logger.info(f"📋 Tablo listesi: {', '.join(sorted(existing_tables))}")

            expected_tables = [
                "users",
                "students",
                "exam_attempts",
                "universities",
                "departments",
                "agenda_items",
                "study_sessions",
                "forum_posts",
                "forum_comments",
                "preferences",
                "swipes",
                "chat_messages",
                "recommendations",
            ]
            missing_tables = [tbl for tbl in expected_tables if tbl not in existing_tables]
            if missing_tables:
                api_logger.warning(f"⚠️ Eksik tablolar tespit edildi: {', '.join(missing_tables)}")
                api_logger.warning("⚠️ Bu tablolar oluşturulmaya çalışılacak...")
                try:
                    create_tables(max_retries=1, retry_delay=1)
                    api_logger.info("✅ Eksik tablolar oluşturuldu!")
                except Exception as table_err:
                    api_logger.error(
                        f"❌ Eksik tablolar oluşturulamadı (non-critical): {table_err}"
                    )
            else:
                api_logger.info("✅ Tüm beklenen tablolar mevcut!")
        except Exception as table_check_err:
            api_logger.warning(
                f"⚠️ Tablo kontrolü sırasında hata (non-critical): {table_check_err}"
            )

    yield
    
    # Shutdown
    api_logger.info("=" * 60)
    api_logger.info("🛑 Shutting down application...")
    api_logger.info("=" * 60)
    # Shutdown
    api_logger.info("Shutting down application...")
    try:
        from services.ml_training_scheduler import shutdown_ml_training_scheduler

        shutdown_ml_training_scheduler()
    except Exception as sched_err:
        api_logger.warning(f"⚠️ APScheduler shutdown issue: {sched_err}")
    api_logger.info("Application shutdown complete")


app = FastAPI(
    title="kAIzen API",
    description="""
    ## Yapay Zeka Destekli Üniversite ve Bölüm Öneri Sistemi
    
    Bu API, öğrenci profillerini analiz ederek YÖK Atlas verilerini kullanarak en uygun tercih önerilerini sunar.
    
    ### Özellikler
    
    * **Öğrenci Yönetimi**: Öğrenci profilleri oluşturma, güncelleme ve listeleme
    * **Puan Hesaplama**: TYT ve AYT netlerinden otomatik puan hesaplama
    * **Üniversite Verileri**: Üniversite ve bölüm bilgilerini listeleme
    * **Yapay Zeka Önerileri**: Öğrenci profiline göre kişiselleştirilmiş tercih önerileri
    * **Filtreleme**: Şehir, üniversite türü, alan türü gibi kriterlere göre filtreleme
    
    ### Kullanım
    
    1. Öğrenci profili oluşturun
    2. Deneme sonuçlarınızı girin
    3. Tercihlerinizi belirtin
    4. Yapay zeka destekli önerileri alın
    
    ### API Endpoints
    
    * **Students**: `/api/students/` - Öğrenci yönetimi
    * **Universities**: `/api/universities/` - Üniversite ve bölüm verileri
    * **Recommendations**: `/api/recommendations/` - Tercih önerileri
    """,
    version="1.0.0",
    contact={
        "name": "kAIzen API Support",
        "email": "support@osymrehberi.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    lifespan=lifespan,
    redirect_slashes=True  # Enable automatic trailing slash redirects (for compatibility)
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Response compression middleware (büyük JSON response'lar için)
app.add_middleware(GZipMiddleware, minimum_size=1000)  # 1KB'dan büyük response'ları sıkıştır

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(students.router, prefix="/api/students", tags=["students"])
app.include_router(universities.router, prefix="/api/universities", tags=["universities"])
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["recommendations"])
app.include_router(ml_recommendations.router, prefix="/api/ml", tags=["ml-recommendations"])
app.include_router(exam_attempts.router, prefix="/api/exam-attempts", tags=["exam-attempts"])
app.include_router(coach_chat.router, prefix="/api/chat", tags=["coach-chat"])
app.include_router(preferences.router, prefix="/api/preferences", tags=["preferences"])
app.include_router(discovery.router, prefix="/api/discovery", tags=["discovery"])
app.include_router(chatbot.router, prefix="/api/chatbot", tags=["chatbot"])
app.include_router(profile.router, prefix="/api/profile", tags=["profile"])
app.include_router(forum.router, prefix="/api/forum", tags=["forum"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(agenda.router, prefix="/api/agenda", tags=["agenda"])
app.include_router(study.router, prefix="/api/study", tags=["study"])
app.include_router(targets.router, prefix="/api/targets", tags=["targets"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(ai_analysis.router, prefix="/api/ai", tags=["ai"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(admin_panel.router, prefix="/api/admin", tags=["admin"])


# ✅ Tüm API route'larını logla (router'lar eklendikten sonra - startup'ta)
def log_all_routes():
    """Tüm kayıtlı route'ları logla"""
    api_logger.info("=" * 60)
    api_logger.info("📋 REGISTERED API ROUTES:")
    api_logger.info("=" * 60)
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            methods = ', '.join(sorted(route.methods)) if route.methods else 'N/A'
            api_logger.info(f"  {methods:20} {route.path}")
        elif hasattr(route, 'path'):
            # Route without methods (e.g., sub-applications)
            api_logger.info(f"  {'N/A':20} {route.path}")
    api_logger.info("=" * 60)


@app.get("/")
async def root():
    return {"message": "kAIzen API - Yapay zeka destekli üniversite öneri sistemi"}


@app.get("/health")
async def health_check():
    """Basit health check endpoint"""
    return {"status": "healthy", "service": "osym-rehberi-api"}


@app.get("/api/health/db")
async def health_check_database_simple():
    """
    ✅ Basit veritabanı health check endpoint
    
    PostgreSQL bağlantısını test eder ve başarılı/başarısız durumu döner.
    """
    from sqlalchemy import text
    from database import engine
    
    try:
        # ✅ Basit SELECT 1 sorgusu ile bağlantı testi
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            test_value = result.scalar()
            
            if test_value == 1:
                return {
                    "status": "healthy",
                    "database": "connected",
                    "message": "Database connection successful"
                }
            else:
                return {
                    "status": "unhealthy",
                    "database": "error",
                    "message": "Database query returned unexpected value"
                }
    except Exception as e:
        api_logger.error(f"❌ Database health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "message": "Database connection failed"
        }


@app.get("/api/health/db-test")
async def health_check_database_test():
    """
    ✅ Veritabanı bağlantısını ve User tablosunu test eden endpoint
    
    - Veritabanı bağlantısını test eder
    - User tablosundan basit bir okuma yapar
    - Sequence durumunu kontrol eder
    """
    from sqlalchemy import text, inspect
    from database import engine, get_db
    from models import User
    
    try:
        db = next(get_db())
        try:
            # ✅ 1. Basit bağlantı testi
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1 as test"))
                test_value = result.scalar()
                if test_value != 1:
                    raise Exception("Database query returned unexpected value")
            
            # ✅ 2. User tablosundan okuma testi
            user_count = db.query(User).count()
            
            # ✅ 3. User tablosundan ilk kaydı çek (eğer varsa)
            first_user = db.query(User).first()
            first_user_info = None
            if first_user:
                first_user_info = {
                    "id": first_user.id,
                    "email": first_user.email,
                    "name": first_user.name,
                    "is_active": first_user.is_active
                }
            
            # ✅ 4. Sequence durumunu kontrol et (users tablosu için)
            inspector = inspect(engine)
            sequence_info = None
            try:
                seq_result = db.execute(text("SELECT pg_get_serial_sequence('users', 'id')"))
                sequence_name = seq_result.scalar()
                if sequence_name:
                    curr_val_result = db.execute(text(f"SELECT currval(:seq)"), {"seq": sequence_name})
                    curr_val = curr_val_result.scalar()
                    next_val_result = db.execute(text(f"SELECT nextval(:seq)"), {"seq": sequence_name})
                    next_val = next_val_result.scalar()
                    # nextval kullandığımız için geri al
                    db.execute(text(f"SELECT setval(:seq, :val, false)"), {"seq": sequence_name, "val": curr_val})
                    db.commit()
                    
                    sequence_info = {
                        "sequence_name": sequence_name,
                        "current_value": curr_val,
                        "next_value": next_val
                    }
            except Exception as seq_error:
                sequence_info = {"error": str(seq_error)}
            
            return {
                "status": "healthy",
                "database": "connected",
                "tests": {
                    "connection": "success",
                    "user_table_read": "success",
                    "user_count": user_count,
                    "first_user": first_user_info,
                    "sequence_status": sequence_info
                },
                "message": "Database connection and User table test successful"
            }
        finally:
            db.close()
            
    except Exception as e:
        api_logger.error(f"❌ Database test failed: {str(e)}")
        import traceback
        api_logger.error(traceback.format_exc())
        return {
            "status": "unhealthy",
            "database": "error",
            "error": str(e),
            "message": "Database test failed"
        }


@app.get("/api/health-check-db")
async def health_check_database():
    """
    ✅ Veritabanı bağlantısını test eden detaylı health check endpoint
    
    PostgreSQL bağlantısını kontrol eder ve veritabanı bilgilerini döner.
    """
    from sqlalchemy import text, inspect
    from database import engine, get_db
    
    try:
        # ✅ 1. Basit bağlantı testi
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            test_value = result.scalar()
            
            if test_value != 1:
                raise Exception("Database query returned unexpected value")
        
        # ✅ 2. PostgreSQL versiyon bilgisi
        with engine.connect() as conn:
            version_result = conn.execute(text("SELECT version()"))
            pg_version = version_result.scalar()
        
        # ✅ 3. Veritabanı adı ve kullanıcı bilgisi
        with engine.connect() as conn:
            db_info_result = conn.execute(text("SELECT current_database(), current_user"))
            db_info = db_info_result.fetchone()
            db_name = db_info[0] if db_info else "unknown"
            db_user = db_info[1] if db_info else "unknown"
        
        # ✅ 4. Tablo sayısı
        inspector = inspect(engine)
        table_count = len(inspector.get_table_names())
        
        # ✅ 5. Connection pool durumu
        pool = engine.pool
        pool_status = {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalid()
        }
        
        return {
            "status": "healthy",
            "database": {
                "type": "PostgreSQL",
                "version": pg_version.split(",")[0] if pg_version else "unknown",  # Sadece versiyon numarası
                "name": db_name,
                "user": db_user,
                "connection": "successful",
                "table_count": table_count
            },
            "connection_pool": pool_status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        import traceback
        api_logger.error(f"❌ Database health check failed: {str(e)}")
        api_logger.error(f"❌ Traceback: {traceback.format_exc()}")
        
        return {
            "status": "unhealthy",
            "database": {
                "type": "PostgreSQL",
                "connection": "failed",
                "error": str(e)
            },
            "timestamp": datetime.now().isoformat()
        }
