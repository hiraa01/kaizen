# kAIzen

Yapay zeka destekli üniversite ve bölüm öneri sistemi. Öğrenci profillerini ve deneme sonuçlarını analiz ederek YÖK Atlas verileriyle kişiselleştirilmiş tercih önerileri sunar.

## Proje amacı

- Öğrenci profilini ve deneme sonuçlarını analiz etme
- YÖK Atlas verileriyle bölüm ve üniversite önerisi
- Koç sohbeti ve ML destekli tercih sıralaması
- İleride KPSS, DGS, ALES gibi sınav modülleri için genişletilebilir yapı

## Teknoloji yığını

### Backend
- **FastAPI** (Python) — REST API
- **SQLAlchemy** — ORM
- **PostgreSQL** — Veritabanı (Docker)
- **Redis + Celery** — Arka plan görevleri
- **scikit-learn** — ML öneri modelleri

### Frontend (mobil)
- **Flutter** (Dart) — Android / iOS
- **Riverpod** — Durum yönetimi
- **Dio** — HTTP istemcisi
- API adresi: `frontend/lib/core/config/app_config.dart`

### DevOps
- **Docker Compose** — `docker/docker-compose.yml`
- **PostgreSQL** — host port `5435`

## Hızlı başlangıç (Windows)

```batch
setup_windows.bat
```

veya geliştirme oturumu (backend + ADB reverse + Flutter):

```batch
start_dev.bat
```

### Docker ile backend

```bash
cd docker
docker compose up -d backend db redis
```

### Servis adresleri (yerel geliştirme)

Aşağıdaki adresler **yalnızca yerel geliştirme ortamı** içindir (Docker Compose ile ayağa kalkan servisler); production/staging dağıtımında bunların yerini gerçek alan adı ve reverse proxy alır.

| Servis | Yerel adres |
|--------|--------|
| Backend API | http://localhost:8003 |
| Swagger UI | http://localhost:8003/docs |
| Health | http://localhost:8003/health |
| PostgreSQL (host) | localhost:5435 |

> Container içinde uvicorn **8000** portunda dinler; host tarafında **8003** ile eşlenir (`8003:8000`). `frontend` servisi `docker-compose.yml` içinde şu an devre dışı (yorum satırı) — mobil uygulamayı Flutter SDK ile çalıştırın (aşağıya bakın).

### Mobil cihaz (USB)

```bash
adb reverse tcp:8003 tcp:8003
```

Uygulama varsayılan olarak `http://127.0.0.1:8003/api` adresini dener. WiFi için bilgisayar IP'nizi verin:

```bash
flutter run --dart-define=DEFAULT_LAN_HOST=192.168.x.x
```

Emülatör:

```bash
flutter run --dart-define=ANDROID_USE_EMULATOR_HOST=true
```

### Ortam değişkenleri

`docker/.env.example` dosyasını `docker/.env` olarak kopyalayıp API anahtarlarını doldurun. Ayrıntı: `docker/README_ENV.md`.

## Proje yapısı

```
osym_rehberi/
├── backend/           # FastAPI
│   ├── routers/       # API endpoint'leri
│   ├── services/      # İş mantığı, AI, ML
│   └── main.py
├── frontend/          # Flutter mobil uygulama
│   └── lib/
│       ├── core/      # config, services, theme
│       └── features/  # Özellik modülleri
├── docker/            # docker-compose.yml
├── scripts/           # Yedekleme, adb reverse
├── start_dev.bat      # Geliştirme başlatıcı
└── README.md
```

## API özeti

| Alan | Örnek |
|------|--------|
| Auth | `POST /api/auth/register`, `POST /api/auth/login` |
| Öğrenci | `GET/POST /api/students/` |
| Üniversiteler | `GET /api/universities/`, `GET /api/universities/cities/` |
| Öneriler | `POST /api/recommendations/generate/{student_id}` |
| Koç sohbeti | `POST /api/chat/coach` |
| ML | `POST /api/ml/train-models`, `GET /api/ml/model-status` |
| Raporlar | `GET /api/reports/student/{id}/exam-attempts.csv` |

Tam liste (backend çalışırken): http://localhost:8003/docs

## Öneri sistemi

1. **Uyumluluk skoru** — puan, sıralama, alan uyumu
2. **Başarı olasılığı** — taban puan ve geçmiş veriler
3. **Tercih skoru** — şehir, üniversite türü, burs, ilgi alanları

## Veri kaynakları

- YÖK Atlas — üniversite ve bölüm verileri
- ÖSYM — sınav istatistikleri
- Kullanıcı girişi — deneme netleri ve tercihler

## Ek dokümantasyon

- `QUICK_START.md` — kısa kurulum
- `USAGE_GUIDE.md` — kullanım kılavuzu
- `README_TR.md` — Türkçe detaylı açıklama
- `ENGINEERING_REQUIREMENTS_CHECKLIST.md` — proje gereksinimleri eşlemesi
- `ML_MODEL_TRAINING.md` — ML model eğitimi

## Lisans

MIT
