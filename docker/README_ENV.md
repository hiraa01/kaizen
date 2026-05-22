# Ortam değişkenleri (docker/.env)

## Kurulum

1. Şablonu kopyalayın:

```bash
cd docker
copy .env.example .env
```

(Linux/macOS: `cp .env.example .env`)

2. `.env` içinde en azından `GEMINI_API_KEY` değerini doldurun (koç sohbeti için).

3. Servisleri yeniden başlatın:

```bash
docker compose down
docker compose up -d backend db redis
```

## Doğrulama

```bash
docker exec osym_rehberi_backend printenv GEMINI_API_KEY
docker logs osym_rehberi_backend --tail 30
```

Flutter uygulamasında koç sohbetini deneyin. `"LLM API anahtarı tanımlı değil"` hatası alırsanız `.env` dosyasını ve container yeniden başlatmayı kontrol edin.

## Değişkenler

| Değişken | Açıklama |
|----------|----------|
| `GEMINI_API_KEY` | Gemini API (birincil, `LLM_PROVIDER=gemini`) |
| `GOOGLE_API_KEY` | Yedek / Groq yolu |
| `GROQ_API_KEY` | Groq API (`LLM_PROVIDER=groq`) |
| `LLM_PROVIDER` | `gemini` veya `groq` (varsayılan: gemini) |
| `JWT_SECRET_KEY` | Oturum imzalama (üretimde zorunlu değiştirin) |
| `GOOGLE_OAUTH_CLIENT_ID` | Google ile giriş doğrulama |
| `ADMIN_USER_IDS` | Admin paneli için kullanıcı ID listesi |

Gemini model adı `backend/services/ai_service.py` içinde `GEMINI_MODEL` ile ayarlanır (varsayılan: `gemini-1.5-flash`). `gemini-pro` artık desteklenmez.

## Güvenlik

- `docker/.env` dosyasını git'e eklemeyin.
- Örnek anahtar veya gerçek anahtarları README'ye yazmayın; yalnızca `.env` kullanın.
