# kAIzen - Kullanım Kılavuzu

## 🚀 Hızlı Başlangıç

### Gereksinimler
- Docker Desktop
- Docker Compose

### Kurulum

1. **Projeyi klonlayın:**
```bash
git clone <repository-url>
cd osym_rehberi
```

2. **Docker konteynerlarını başlatın:**
```bash
cd docker
docker-compose up --build
```

3. **Servislere erişim:**
- Backend API: http://localhost:8003
- Flutter mobil: `start_dev.bat` veya `cd frontend && flutter run`
- PostgreSQL: localhost:5435

## 📱 Frontend Kullanımı

### Ana Sayfa
- Uygulama açıldığında ana sayfa görüntülenir
- Hızlı işlemler menüsünden istediğiniz işlemi seçebilirsiniz

### Öğrenci Profili Oluşturma

1. **Profil Oluştur** butonuna tıklayın
2. **Adım 1 - Temel Bilgiler:**
   - Ad soyad girin (zorunlu)
   - E-posta ve telefon (isteğe bağlı)
   - Sınıf seviyesi seçin
   - Sınav türü seçin (TYT, AYT, TYT+AYT)
   - Alan türü seçin (SAY, EA, SÖZ, DİL)

3. **Adım 2 - TYT Netleri:**
   - Türkçe neti girin
   - Matematik neti girin
   - Sosyal Bilimler neti girin
   - Fen Bilimleri neti girin

4. **Adım 3 - AYT Netleri:**
   - Girdiğiniz derslerin netlerini girin
   - Sadece girdiğiniz dersler için net girin

5. **Adım 4 - Tercihler:**
   - Tercih edilen şehirleri seçin
   - Üniversite türü tercihlerini belirtin
   - Bütçe tercihini seçin
   - Burs tercihini belirtin
   - İlgi alanlarını seçin

6. **Kaydet** butonuna tıklayın

### Üniversite ve Bölüm Arama

1. **Üniversiteler** veya **Bölüm Ara** butonuna tıklayın
2. Arama çubuğuna arama terimi girin
3. Filtre butonuna tıklayarak filtreleri uygulayın:
   - Şehir filtreleme
   - Üniversite türü filtreleme
   - Alan türü filtreleme (bölümler için)

### Tercih Önerileri

1. **Tercih Önerileri** butonuna tıklayın
2. Önce bir öğrenci profili oluşturmanız gerekir
3. Profil oluşturduktan sonra:
   - **Yeni Öneriler** butonuna tıklayın
   - Yapay zeka önerilerinizi oluşturun
   - Filtrelerle önerileri daraltın
   - Öneri detaylarını inceleyin

## 🔧 Backend API Kullanımı

### API Dokümantasyonu
- Swagger UI: http://localhost:8003/docs
- ReDoc: http://localhost:8003/redoc

### Temel Endpoints

#### Öğrenci Yönetimi
```bash
# Öğrenci listesi
GET /api/students/

# Öğrenci detayı
GET /api/students/{id}

# Yeni öğrenci oluştur
POST /api/students/
{
  "name": "Ahmet Yılmaz",
  "email": "ahmet@example.com",
  "class_level": "12",
  "exam_type": "TYT+AYT",
  "field_type": "SAY",
  "tyt_turkish_net": 30.0,
  "tyt_math_net": 25.0,
  // ... diğer alanlar
}

# Öğrenci güncelle
PUT /api/students/{id}

# Öğrenci sil
DELETE /api/students/{id}

# Puanları hesapla
POST /api/students/{id}/calculate-scores
```

#### Üniversite Verileri
```bash
# Üniversite listesi
GET /api/universities/

# Bölüm listesi
GET /api/universities/departments/

# Şehir listesi
GET /api/universities/cities/
```

#### Tercih Önerileri
```bash
# Öneri oluştur
POST /api/recommendations/generate/{student_id}

# Öğrenci önerileri
GET /api/recommendations/student/{student_id}

# Öneri istatistikleri
GET /api/recommendations/stats/{student_id}
```

## 🧠 Öneri Sistemi

### Skor Hesaplama

Sistem aşağıdaki faktörleri analiz ederek öneriler oluşturur:

1. **Uyumluluk Skoru (40%)**
   - Puan uyumluluğu
   - Sıralama uyumluluğu
   - Alan uyumluluğu

2. **Başarı Olasılığı (40%)**
   - Öğrenci puanı vs bölüm taban puanı
   - Geçmiş yıl verileri

3. **Tercih Skoru (20%)**
   - Şehir tercihi
   - Üniversite türü tercihi
   - Burs tercihi
   - İlgi alanları

### Öneri Türleri

- **Güvenli Tercih**: Yüksek başarı olasılığı (%80+)
- **Gerçekçi Tercih**: Orta başarı olasılığı (%30-80)
- **Hayal Tercihi**: Düşük başarı olasılığı (%30-)

## 🐳 Docker Kullanımı

### Servisleri Başlatma
```bash
# Tüm servisleri başlat
docker-compose up

# Arka planda çalıştır
docker-compose up -d

# Sadece backend
docker-compose up backend

# Sadece frontend
docker-compose up frontend
```

### Logları Görüntüleme
```bash
# Backend logları
docker-compose logs backend

# Frontend logları
docker-compose logs frontend

# Tüm loglar
docker-compose logs
```

### Servisleri Durdurma
```bash
# Servisleri durdur
docker-compose down

# Volumeleri de sil
docker-compose down -v
```

## 🧪 Test Çalıştırma

### Backend Testleri
```bash
cd backend
pip install -r requirements-test.txt
pytest
```

### Frontend Testleri
```bash
cd frontend
flutter test
```

## 🔧 Geliştirme

### Backend Geliştirme
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend Geliştirme
```bash
cd frontend
flutter run -d web-server --web-hostname 0.0.0.0 --web-port 3000
```

## 📊 Veri Yönetimi

### Örnek Veri Import
```bash
cd backend
python scripts/import_yok_data.py
```

### Veritabanı Yedekleme
```bash
docker-compose exec db pg_dump -U osym_user osym_rehber > backup.sql
```

### Veritabanı Geri Yükleme
```bash
docker-compose exec -T db psql -U osym_user osym_rehber < backup.sql
```

## 🚨 Sorun Giderme

### Yaygın Sorunlar

1. **Port çakışması**
   - 8003, 5435, 6379 portlarının boş olduğundan emin olun

2. **Docker sorunları**
   - Docker Desktop'ın çalıştığından emin olun
   - `docker-compose down` ile temizleyip tekrar başlatın

3. **Veritabanı bağlantı sorunu**
   - PostgreSQL konteynerının çalıştığından emin olun
   - Veritabanı başlatılmasını bekleyin (30-60 saniye)

4. **Frontend build sorunu**
   - `flutter clean` çalıştırın
   - `flutter pub get` ile bağımlılıkları yeniden yükleyin

### Log Kontrolü
```bash
# Backend logları
docker-compose logs backend | tail -50

# Frontend logları
docker-compose logs frontend | tail -50

# Veritabanı logları
docker-compose logs db | tail -50
```

## 📞 Destek

Sorunlarınız için:
- GitHub Issues: [Repository Issues](https://github.com/your-repo/issues)
- E-posta: support@osymrehberi.com

## 📄 Lisans

Bu proje MIT lisansı altında lisanslanmıştır.
