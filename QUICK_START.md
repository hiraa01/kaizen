# kAIzen — Hızlı başlangıç

## Gereksinimler

- Docker Desktop
- Flutter SDK (mobil geliştirme için)
- Android SDK + USB hata ayıklama (gerçek cihaz için)

## 1. Backend

```bash
cd docker
docker compose up -d backend db redis
```

Sağlık kontrolü:

```bash
curl http://localhost:8003/health
```

- API: http://localhost:8003
- Swagger: http://localhost:8003/docs

Manuel image (isteğe bağlı):

```bash
cd backend
docker build -t osym-backend .
docker run -d -p 8003:8000 --name osym-backend osym-backend
```

## 2. Mobil uygulama

Önerilen (Windows):

```batch
start_dev.bat
```

Manuel:

```bash
adb reverse tcp:8003 tcp:8003
cd frontend
flutter pub get
flutter run
```

## 3. API bağlantı ayarları

Adres mantığı `frontend/lib/core/config/app_config.dart` içindedir; sabit URL yazmaya gerek yoktur.

| Senaryo | URL |
|---------|-----|
| USB + adb reverse | `http://127.0.0.1:8003/api` |
| WiFi (LAN) | `http://<PC_IP>:8003/api` |
| Emülatör | `http://10.0.2.2:8003/api` (`ANDROID_USE_EMULATOR_HOST=true`) |

WiFi IP override:

```bash
flutter run --dart-define=DEFAULT_LAN_HOST=192.168.x.x
```

Tam override:

```bash
flutter run --dart-define=API_BASE_URL=http://192.168.x.x:8003/api
```

## 4. Uygulama akışı

1. Onboarding (atlanabilir)
2. Kayıt / giriş
3. İlk kurulum (deneme, net, tercih)
4. Ana uygulama: ana sayfa, denemeler, hedef, öneriler, profil, koç sohbeti

## Sorun giderme

**Backend yanıt vermiyor**

```bash
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml logs backend
```

**Telefon API'ye ulaşamıyor**

```bash
adb reverse tcp:8003 tcp:8003
curl http://127.0.0.1:8003/health
```

**Flutter derleme hataları**

```bash
cd frontend
flutter clean
flutter pub get
flutter run
```

## İlgili dosyalar

- `docker/.env.example` — ortam değişkenleri şablonu
- `README.md` — genel bakış
- `USAGE_GUIDE.md` — detaylı kullanım
