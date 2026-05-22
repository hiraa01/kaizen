# ML model eğitimi

## Durum

Koç sohbeti hazır LLM API kullanır (Gemini / Groq, eğitim gerektirmez).  
ML öneri motoru modelleri ayrıca eğitilir ve `ml_models` volume'unda saklanır.

## Eğitim

### Docker içinde

```bash
docker exec osym_rehberi_backend python scripts/train_ml_models.py
```

### API ile

Backend çalışırken:

```bash
curl -X POST http://localhost:8003/api/ml/train-models
```

Swagger: http://localhost:8003/docs → `POST /api/ml/train-models`

### Model durumu

```bash
curl http://localhost:8003/api/ml/model-status
```

Öğrenci önerileri:

```bash
curl http://localhost:8003/api/ml/ml-recommendations/{student_id}
```

## Çıktı dosyaları

- `backend/ml_models/compatibility_model.pkl`
- `backend/ml_models/compatibility_scaler.pkl`
- `backend/ml_models/success_model.pkl`
- `backend/ml_models/success_scaler.pkl`
- `backend/ml_models/preference_model.pkl`
- `backend/ml_models/preference_scaler.pkl`

Docker volume `ml_models` ile kalıcıdır.

## Notlar

- İlk eğitim simüle edilmiş veri ile yapılabilir.
- Periyodik güncelleme Celery worker üzerinden yapılandırılabilir.
