@echo off
setlocal EnableExtensions

set "OUTPUT_DIR=%~dp0..\backups"
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set "DATE_STR=%%c-%%a-%%b"
for /f "tokens=1-3 delims=:., " %%a in ("%time%") do set "TIME_STR=%%a%%b%%c"
set "BACKUP_FILE=%OUTPUT_DIR%\osym_backup_%DATE_STR%_%TIME_STR%.sql"

echo [INFO] Veritabani yedegi aliniyor...
docker exec -t osym_rehberi_db pg_dump -U osym_user -d osym_rehber > "%BACKUP_FILE%"
if errorlevel 1 (
  echo [HATA] Yedek alma basarisiz.
  exit /b 1
)

echo [OK] Yedek olusturuldu: %BACKUP_FILE%
