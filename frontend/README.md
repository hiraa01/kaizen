# kAIzen — Flutter mobil uygulama

ÖSYM Rehberi projesinin Android / iOS istemcisi.

## Geliştirme

Önerilen başlatma (proje kökünden):

```batch
..\start_dev.bat
```

Manuel:

```bash
adb reverse tcp:8003 tcp:8003
flutter pub get
flutter run
```

Backend `http://localhost:8003` üzerinde çalışmalıdır (`docker compose`).

## API yapılandırması

`lib/core/config/app_config.dart` — USB, WiFi ve dart-define ile adres seçimi.

```bash
flutter run --dart-define=DEFAULT_LAN_HOST=192.168.x.x
flutter run --dart-define=API_BASE_URL=http://192.168.x.x:8003/api
flutter run --dart-define=ANDROID_USE_EMULATOR_HOST=true
```

## Proje yapısı

```
lib/
├── core/       # config, services, theme, widgets
└── features/   # auth, dashboard, coach_chat, recommendations, ...
```

## Tasarım prototipleri

`stitch_anasayfa/` HTML mockup dosyalarıdır; çalışan uygulama `lib/` altındadır.
