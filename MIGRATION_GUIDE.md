# PostgreSQL Migration Rehberi

Bu rehber, SQLite'tan PostgreSQL'e geçiş için adım adım talimatlar içerir. **Yeni kurulumlar** doğrudan `docker compose` ile PostgreSQL kullanır; ayrıntı için `DATABASE_INFO.md` ve `README.md` bakın.

## ❓ Sık Sorulan Sorular

### PostgreSQL'i bilgisayarıma yüklemem gerekiyor mu?

**HAYIR!** PostgreSQL zaten Docker container'ında çalışıyor. Yerel olarak PostgreSQL yüklemenize gerek yok. Docker Compose otomatik olarak PostgreSQL container'ını başlatır.

### Migration'ı sürekli yapmam gerekiyor mu?

**HAYIR!** Migration sadece **bir kez** yapılır:
- ✅ İlk kurulumda (tabloları oluşturmak için)
- ✅ Veritabanını sıfırladığınızda
- ✅ Yeni bir ortam kurduğunuzda

Normal kullanımda migration'a gerek yok. Uygulama çalışırken otomatik olarak veriler kaydedilir ve okunur.

### Ne zaman migration yapmalıyım?

- 🆕 İlk kez kurulum yapıyorsanız
- 🔄 Veritabanını sıfırlamak istiyorsanız
- 📦 YÖK verilerini yeniden yüklemek istiyorsanız

## 📋 Ön Gereksinimler

1. Docker ve Docker Compose yüklü olmalı
2. Backend container'ı çalışıyor olmalı
3. PostgreSQL container'ı çalışıyor olmalı (Docker otomatik başlatır)

## 🚀 Adım 1: Docker Container'ları Kontrol Et

Önce container'ların çalıştığını kontrol edin:

```bash
docker ps
```

Şu container'ları görmelisiniz:
- `osym_rehberi_backend`
- `osym_rehberi_db` (PostgreSQL)
- `osym_rehberi_redis` (opsiyonel)

Eğer çalışmıyorsa:

```bash
cd docker
docker compose up -d
```

## 🔧 Adım 2: Backend Container'ına Gir

```bash
docker exec -it osym_rehberi_backend bash
```

## 📦 Adım 3: PostgreSQL Tablolarını Oluştur

Container içindeyken:

```bash
python scripts/init_postgresql.py
```

**Not:** Docker volume mapping nedeniyle script'ler `/app/scripts/` altında, `/app/backend/scripts/` altında değil.

Bu script:
- ✅ Tüm tabloları oluşturur (students, exam_attempts, universities, departments, vb.)
- ✅ Index'leri oluşturur (performans için)
- ✅ Veri durumunu kontrol eder

**Beklenen Çıktı:**
```
============================================================
🚀 POSTGRESQL VERİTABANI BAŞLATMA
============================================================

============================================================
📋 PostgreSQL TABLOLARI OLUŞTURULUYOR...
============================================================
✅ Tüm tablolar başarıyla oluşturuldu!

📊 Oluşturulan tablolar (X adet):
   - students
   - exam_attempts
   - universities
   - departments
   - recommendations
   - users
   ...

============================================================
⚡ PERFORMANS İNDEX'LERİ OLUŞTURULUYOR...
============================================================
✅ Tüm performans index'leri oluşturuldu!

============================================================
🔍 VERİ KONTROLÜ YAPILIYOR...
============================================================
📚 Üniversiteler: 0 adet
📖 Bölümler: 0 adet
👤 Öğrenciler: 0 adet
📝 Denemeler: 0 adet

⚠️  UYARI: YÖK verileri yüklenmemiş!
   YÖK verilerini yüklemek için şu komutu çalıştırın:
   python scripts/seed_yok_data.py
```

## 📚 Adım 4: YÖK Verilerini Yükle

İki seçeneğiniz var:

### Seçenek A: Örnek Veriler (Hızlı Test İçin)

```bash
python scripts/seed_yok_data.py
```

### Seçenek B: Gerçek Excel Verileri (backend/data klasöründen) - ÖNERİLEN

```bash
python scripts/import_osym_excel.py
```

Bu script `backend/data` klasöründeki tüm Excel dosyalarını (2022-2025) otomatik bulur ve PostgreSQL'e aktarır:
- ✅ Üniversiteler (şehir bilgisiyle)
- ✅ Bölümler (program adlarıyla)
- ✅ Puanlar (min_score, max_score)
- ✅ Kontenjanlar
- ✅ Yerleşen öğrenci sayıları
- ✅ Puan türleri (SAY/EA/SÖZ/DİL)

**Not:** 
- Excel dosyalarının `backend/data` klasöründe olduğundan emin olun
- Script otomatik olarak tüm `.xlsx` ve `.xls` dosyalarını bulur
- Her dosya için yıl bilgisi otomatik çıkarılır

Bu script:
- ✅ Üniversiteleri yükler
- ✅ Bölümleri yükler
- ✅ Şehirleri yükler
- ✅ Puan hesaplama katsayılarını yükler

**Beklenen Çıktı:**
```
============================================================
YÖK ATLAS VERİLERİ YÜKLENİYOR
============================================================

📋 Database tabloları oluşturuluyor...
✅ Tablolar oluşturuldu

📚 Programlar yükleniyor...
✅ X program yüklendi

📚 Üniversiteler yükleniyor...
✅ X üniversite yüklendi

============================================================
✅ TÜM VERİLER BAŞARIYLA YÜKLENDİ!
============================================================
```

## ✅ Adım 5: Veritabanını Kontrol Et (Opsiyonel)

PostgreSQL container'ına bağlanarak verileri kontrol edebilirsiniz:

```bash
# Yeni bir terminal açın
docker exec -it osym_rehberi_db psql -U osym_user -d osym_rehber

# Tabloları listele
\dt

# Üniversite sayısını kontrol et
SELECT COUNT(*) FROM universities;

# Bölüm sayısını kontrol et
SELECT COUNT(*) FROM departments;

# Çıkış
\q
```

## 🔄 Adım 6: Backend'i Yeniden Başlat

Migration tamamlandıktan sonra backend'i yeniden başlatın:

```bash
# Container'dan çık
exit

# Backend container'ını yeniden başlat
docker restart osym_rehberi_backend
```

## 📱 Adım 7: Uygulamayı Test Et

1. Flutter uygulamasını açın
2. Yeni bir kullanıcı kaydı oluşturun
3. Deneme ekleyin
4. Dashboard'da verilerin göründüğünü kontrol edin

## ⚠️ Sorun Giderme

### Hata: "Connection refused" veya "Could not connect to database"

**Çözüm:**
```bash
# PostgreSQL container'ının çalıştığını kontrol et
docker ps | grep osym_rehberi_db

# Çalışmıyorsa başlat
docker compose up -d db

# Health check'i bekle (30 saniye)
docker logs osym_rehberi_db
```

### Hata: "Table already exists"

**Çözüm:**
Bu normaldir, script tabloları zaten oluşturmuştur. Devam edebilirsiniz.

### Hata: "Student not found" (404)

**Çözüm:**
1. Migration'ı tamamladığınızdan emin olun
2. Yeni bir kullanıcı kaydı oluşturun (eski student_id'ler geçersiz olabilir)
3. SharedPreferences'ı temizleyin (uygulamayı silip yeniden yükleyin)

### Veriler Yüklenmiyor

**Çözüm:**
```bash
# Backend loglarını kontrol et
docker logs osym_rehberi_backend

# PostgreSQL loglarını kontrol et
docker logs osym_rehberi_db

# Container'ları yeniden başlat
docker compose restart
```

## 📝 Notlar

- **Eski Veriler:** SQLite'taki eski veriler PostgreSQL'e otomatik aktarılmaz. Yeni kullanıcı kaydı oluşturmanız gerekir.
- **YÖK Verileri:** `seed_yok_data.py` script'i örnek veriler yükler. Gerçek YÖK verilerini yüklemek için `import_yok_data.py` kullanabilirsiniz.
- **Performans:** Index'ler otomatik oluşturulur, ancak büyük veri setleri için ek optimizasyon gerekebilir.

## 🎯 Hızlı Başlangıç (Özet)

```bash
# 1. Container'ları başlat
cd docker
docker compose up -d

# 2. Backend container'ına gir
docker exec -it osym_rehberi_backend bash

# 3. Tabloları oluştur
python scripts/init_postgresql.py

# 4. YÖK verilerini yükle
python scripts/seed_yok_data.py

# 5. Çık
exit

# 6. Backend'i yeniden başlat
docker restart osym_rehberi_backend
```

## ✅ Başarı Kontrolü

Migration başarılı olduysa:
- ✅ Backend loglarında "Database tables created successfully" mesajı görünür
- ✅ PostgreSQL'de tablolar oluşturulmuştur
- ✅ YÖK verileri yüklenmiştir
- ✅ Uygulamada yeni kullanıcı kaydı oluşturulabilir
- ✅ Denemeler kaydedilebilir ve görüntülenebilir

