@echo off
setlocal EnableExtensions EnableDelayedExpansion
title kAIzen - Windows Kurulum

echo ==========================================
echo   kAIzen Windows Kurulum Araci
echo ==========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [HATA] Python bulunamadi. Python 3.11+ kurup tekrar deneyin.
  exit /b 1
)

where docker >nul 2>&1
if errorlevel 1 (
  echo [HATA] Docker bulunamadi. Docker Desktop kurup tekrar deneyin.
  exit /b 1
)

where flutter >nul 2>&1
if errorlevel 1 (
  echo [HATA] Flutter bulunamadi. Flutter SDK kurup PATH e ekleyin.
  exit /b 1
)

echo [1/5] Backend Python bagimliliklari yukleniyor...
python -m pip install -r backend\requirements.txt
if errorlevel 1 exit /b 1

echo [2/5] Flutter bagimliliklari yukleniyor...
pushd frontend
flutter pub get
if errorlevel 1 (
  popd
  exit /b 1
)
popd

echo [3/5] Docker servisleri baslatiliyor...
docker compose -f docker\docker-compose.yml up -d --build
if errorlevel 1 exit /b 1

echo [4/5] ADB komutu kontrol ediliyor...
where adb >nul 2>&1
if errorlevel 1 (
  echo [UYARI] adb bulunamadi. Mobil hata ayiklama icin Android platform-tools gerekli.
) else (
  echo [OK] adb bulundu.
)

echo [5/5] Kurulum tamamlandi.
echo.
echo Sonraki adim:
echo - Mobilde calistirmak icin: start_dev.bat
echo - Yalnizca backend: docker compose -f docker\docker-compose.yml up -d backend db redis
echo.
pause
