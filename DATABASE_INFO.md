# Veritabanı bilgisi

## Genel

Geliştirme ve Docker ortamında **PostgreSQL** kullanılır. Veriler named volume ile kalıcıdır.

## Konum

| Bileşen | Container | Host port | Volume |
|---------|-----------|-----------|--------|
| PostgreSQL | `osym_rehberi_db` | 5435 | `postgres_data` |
| Backend | `osym_rehberi_backend` | 8003 → 8000 | `backend_logs`, `ml_models` |

Volume listesi:

```bash
docker volume ls
docker volume inspect docker_postgres_data
```

## Bağlantı (container içinden)

```bash
docker exec -it osym_rehberi_db psql -U osym_user -d osym_rehber
```

## Saklanan veriler

- Kullanıcılar ve oturum bilgileri
- Öğrenci profilleri ve tercihler
- Deneme kayıtları (`exam_attempts`)
- Tercih önerileri
- Üniversite ve bölüm kataloğu

## Yedekleme

```batch
scripts\db_backup.bat
scripts\db_restore.bat
```

## Notlar

- Container silinse bile `postgres_data` volume'u veriyi korur.
- `docker compose` dosyası: `docker/docker-compose.yml`
- Eski SQLite tabanlı kurulumlar kaldırıldı; yeni kurulumda yalnızca PostgreSQL geçerlidir.
