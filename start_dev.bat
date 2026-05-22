@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0"
set "DOCKER_COMPOSE_FILE=%ROOT_DIR%docker\docker-compose.yml"

echo [1/3] Backend servisleri kontrol ediliyor...
if exist "%DOCKER_COMPOSE_FILE%" (
    docker info >nul 2>&1
    if errorlevel 1 (
        echo [!] Docker Desktop calismiyor. Lutfen Docker Desktop acip tekrar deneyin.
        echo     Not: Backend calismadan veriler yuklenmez.
        pause
        exit /b 1
    )

    docker compose -f "%DOCKER_COMPOSE_FILE%" up -d backend db redis >nul 2>&1
    if errorlevel 1 (
        echo [!] Docker servisleri baslatilamadi.
        echo     Komut: docker compose -f "%DOCKER_COMPOSE_FILE%" up -d backend db redis
        pause
        exit /b 1
    )

    powershell -NoProfile -Command "$ok=$false; 1..25 | ForEach-Object { try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:8003/health' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { $ok=$true; break } } catch {}; Start-Sleep -Seconds 2 }; if (-not $ok) { exit 1 }"
    if errorlevel 1 (
        echo [!] Backend saglik kontrolu basarisiz: http://127.0.0.1:8003/health
        echo     Ayrinti: docker compose -f "%DOCKER_COMPOSE_FILE%" logs backend
        pause
        exit /b 1
    )
    echo [OK] Backend hazir.
) else (
    echo [!] Docker compose dosyasi bulunamadi: "%DOCKER_COMPOSE_FILE%"
    pause
    exit /b 1
)

rem PATH sirasinda yanlis adb "unknown command reverse" verebilir
set "ADB_EXE="
if defined ANDROID_HOME if exist "%ANDROID_HOME%\platform-tools\adb.exe" (
    set "ADB_EXE=%ANDROID_HOME%\platform-tools\adb.exe"
)
if not defined ADB_EXE if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" (
    set "ADB_EXE=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
)
if not defined ADB_EXE set "ADB_EXE=adb"

echo [2/3] ADB reverse kuruluyor (USB tunel: telefon:8003 -^> bilgisayar:8003)...
echo       ADB: "%ADB_EXE%"
"%ADB_EXE%" devices
"%ADB_EXE%" reverse --remove tcp:8003 2>nul
"%ADB_EXE%" reverse tcp:8003 tcp:8003
if errorlevel 1 (
    echo [!] ADB reverse basarisiz.
    echo     - Telefon USB ile bagli ve USB hata ayiklama acik mi?
    echo     - CMD icinde: "%ADB_EXE%" reverse tcp:8003 tcp:8003
    echo     - PowerShell: ^& "%ADB_EXE%" reverse tcp:8003 tcp:8003
    echo     WiFi icin AppConfig DEFAULT_LAN_HOST bilgisayar IP adresinize gore ayarli olmali.
) else (
    echo [OK] USB tunel aktif.
)

echo [3/3] Flutter baslatiliyor...
echo       Once USB/127.0.0.1:8003, gerekirse WiFi.
echo       Saglik: http://127.0.0.1:8003/health
echo.
pushd frontend
if defined GOOGLE_SERVER_CLIENT_ID (
  flutter run -t lib/main.dart --dart-define=GOOGLE_SERVER_CLIENT_ID=%GOOGLE_SERVER_CLIENT_ID%
) else (
  flutter run -t lib/main.dart
)
popd
