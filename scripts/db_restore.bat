@echo off
setlocal EnableExtensions

if "%~1"=="" (
  echo Kullanim: db_restore.bat "tam_yol_backup.sql"
  exit /b 1
)

set "BACKUP_FILE=%~1"
if not exist "%BACKUP_FILE%" (
  echo [HATA] Yedek dosyasi bulunamadi: %BACKUP_FILE%
  exit /b 1
)

echo [UYARI] Mevcut veritabani geri yukleme ile degisecek.
set /p "CONFIRM=Devam etmek icin EVET yazin: "
if /I not "%CONFIRM%"=="EVET" (
  echo Islem iptal edildi.
  exit /b 0
)

echo [INFO] Veritabani geri yukleniyor...
type "%BACKUP_FILE%" | docker exec -i osym_rehberi_db psql -U osym_user -d osym_rehber
if errorlevel 1 (
  echo [HATA] Geri yukleme basarisiz.
  exit /b 1
)

echo [OK] Geri yukleme tamamlandi.
