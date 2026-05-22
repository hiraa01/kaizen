# ✅ Migration Sonrası Kontrol Listesi

Migration'ı tamamladıktan sonra yapmanız gerekenler:

## 🔍 1. Veritabanı Kontrolü

### Container içinden kontrol:

```bash
docker exec -it osym_rehberi_backend bash
python -c "
from database import SessionLocal
from models.university import University, Department
from models.student import Student
from models.exam_attempt import ExamAttempt

db = SessionLocal()
print(f'✅ Üniversiteler: {db.query(University).count()}')
print(f'✅ Bölümler: {db.query(Department).count()}')
print(f'✅ Öğrenciler: {db.query(Student).count()}')
print(f'✅ Denemeler: {db.query(ExamAttempt).count()}')
db.close()
"
exit
```

**Beklenen:**
- Üniversiteler: > 0 (en az 100+ olmalı)
- Bölümler: > 0 (en az 1000+ olmalı)
- Öğrenciler: 0 (yeni kayıt olacak)
- Denemeler: 0 (yeni eklenecek)

## 🔄 2. Backend'i Yeniden Başlat

```bash
docker restart osym_rehberi_backend
```

Backend'in düzgün başladığını kontrol edin:

```bash
docker logs osym_rehberi_backend --tail 30
```

**Beklenen:**
- ✅ "Database tables created successfully"
- ✅ "Application started successfully"
- ❌ Hata mesajı olmamalı

## 📱 3. Frontend'i Test Et

1. **Uygulamayı açın**
2. **Yeni bir kullanıcı kaydı oluşturun** (eski student_id'ler geçersiz olabilir)
3. **Deneme ekleyin**
4. **Dashboard'da verilerin göründüğünü kontrol edin**

### Önemli: Eski Veriler

- ❌ Eski SQLite verileri PostgreSQL'e aktarılmaz
- ✅ Yeni kullanıcı kaydı oluşturmanız gerekir
- ✅ SharedPreferences'ı temizleyin (uygulamayı silip yeniden yükleyin)

## 🧪 4. API Endpoint'lerini Test Et

Backend'in çalıştığını kontrol edin:

```bash
# Health check
curl http://localhost:8003/health

# Şehirler listesi
curl http://localhost:8003/api/universities/cities/

# Üniversiteler (ilk 10)
curl http://localhost:8003/api/universities/?skip=0&limit=10
```

**Beklenen:**
- ✅ 200 OK response
- ✅ JSON data dönmeli
- ❌ 404 veya 500 hatası olmamalı

## ⚠️ 5. Sorun Giderme

### Problem: "Öğrenci bulunamadı" (404)

**Çözüm:**
1. Yeni bir kullanıcı kaydı oluşturun
2. Uygulamayı silip yeniden yükleyin (SharedPreferences temizlenir)
3. İlk kurulum adımlarını tekrar yapın

### Problem: Veriler görünmüyor

**Çözüm:**
```bash
# Backend loglarını kontrol et
docker logs osym_rehberi_backend --tail 50

# PostgreSQL'e bağlan ve kontrol et
docker exec -it osym_rehberi_db psql -U osym_user -d osym_rehber
SELECT COUNT(*) FROM universities;
SELECT COUNT(*) FROM departments;
\q
```

### Problem: Timeout hataları

**Çözüm:**
- Backend optimize edildi, ancak ilk yüklemede biraz yavaş olabilir
- İkinci istekte daha hızlı olmalı (cache sayesinde)

## ✅ 6. Başarı Kriterleri

Migration başarılı olduysa:

- ✅ Backend çalışıyor (health check OK)
- ✅ Üniversiteler yüklendi (> 100)
- ✅ Bölümler yüklendi (> 1000)
- ✅ Yeni kullanıcı kaydı oluşturulabiliyor
- ✅ Deneme eklenebiliyor
- ✅ Dashboard'da veriler görünüyor
- ✅ Öneriler çalışıyor

## 🎯 Hızlı Test Komutları

```bash
# 1. Veritabanı durumu
docker exec osym_rehberi_backend python -c "from database import SessionLocal; from models.university import University, Department; db = SessionLocal(); print(f'Üniversiteler: {db.query(University).count()}'); print(f'Bölümler: {db.query(Department).count()}'); db.close()"

# 2. Backend health check
curl http://localhost:8003/health

# 3. Backend logları
docker logs osym_rehberi_backend --tail 20

# 4. PostgreSQL bağlantısı
docker exec osym_rehberi_db psql -U osym_user -d osym_rehber -c "SELECT COUNT(*) FROM universities;"
```

## 📝 Sonraki Adımlar

Migration tamamlandıktan sonra:

1. ✅ **Yeni kullanıcı kaydı oluşturun** (eski veriler geçersiz)
2. ✅ **Uygulamayı test edin** (deneme ekleme, dashboard, öneriler)
3. ✅ **Performansı kontrol edin** (veriler hızlı yüklenmeli)
4. ✅ **Sorun varsa logları kontrol edin**

## 🆘 Yardım Gerekirse

Sorun yaşarsanız:

1. Backend loglarını kontrol edin: `docker logs osym_rehberi_backend`
2. PostgreSQL loglarını kontrol edin: `docker logs osym_rehberi_db`
3. Veritabanı durumunu kontrol edin (yukarıdaki komutlar)
4. Hata mesajlarını paylaşın

