# Veritabanı kalıcılık düzeltmesi (tarihsel)

> **Güncel durum:** Proje PostgreSQL + `postgres_data` volume kullanır (`docker/docker-compose.yml`). Bu belge eski SQLite kurulumu içindir.

## Sorun (eski SQLite kurulumu)
SQLite veritabanı dosyası container içinde `/app/osym_rehber.db` konumundaydı. Container silindiğinde veriler kayboluyordu.

## Çözüm
SQLite dosyası artık persistent volume'da (`/app/data/osym_rehber.db`) saklanıyor.

### Yapılan Değişiklikler

1. **backend/database.py**:
   - SQLite dosyası `/app/data/osym_rehber.db` konumuna taşındı
   - `/app/data` dizini otomatik oluşturuluyor
   - Volume mount: `backend_data:/app/data`

### Container Yeniden Başlatma Sonrası

Container'ı yeniden başlattıktan sonra:
1. Eğer veriler varsa → `/app/data/` altında korunur
2. Eğer yeni kurulumsa → Yeni dosya oluşturulur

### Manuel Veri Taşıma (Gerekirse)

Eğer eski container'da veriler varsa:
```bash
# Eski container'da dosya varsa taşı
docker exec osym_rehberi_backend mkdir -p /app/data
docker exec osym_rehberi_backend mv /app/osym_rehber.db /app/data/osym_rehber.db 2>/dev/null || echo "No file to move"
```

### Volume Kontrolü

Volume'un doğru mount edildiğini kontrol et:
```bash
docker inspect osym_rehberi_backend | grep -A 5 "Mounts"
```

Volume'da verilerin olduğunu kontrol et:
```bash
docker volume inspect osym_rehberi_backend_data
```

## Önemli Notlar

✅ **Artık container silinse bile veriler korunur**
✅ **Volume `backend_data` kalıcı olarak saklanır**
✅ **Backup için volume'u export edebilirsiniz**

## Backup

Volume'u yedeklemek için:
```bash
docker run --rm -v osym_rehberi_backend_data:/data -v $(pwd):/backup alpine tar czf /backup/backend_data_backup.tar.gz -C /data .
```

## Restore

Yedekten geri yüklemek için:
```bash
docker run --rm -v osym_rehberi_backend_data:/data -v $(pwd):/backup alpine sh -c "cd /data && tar xzf /backup/backend_data_backup.tar.gz"
```

