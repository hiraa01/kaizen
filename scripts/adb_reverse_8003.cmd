@echo off
setlocal EnableExtensions
rem CMD den calistirin. Gercek Android SDK adb kullanilir.
rem "unknown command reverse" = PATH te yanlis veya eski adb var.

set "ADB_EXE="
if defined ANDROID_HOME if exist "%ANDROID_HOME%\platform-tools\adb.exe" (
    set "ADB_EXE=%ANDROID_HOME%\platform-tools\adb.exe"
)
if not defined ADB_EXE if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" (
    set "ADB_EXE=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
)

if not defined ADB_EXE (
    echo [X] adb.exe bulunamadi. Beklenen: %LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe
    echo     Android Studio ^> Settings ^> Android SDK ^> SDK Tools ^> Android SDK Platform-Tools
    exit /b 1
)

echo.
echo === Bu betik kullaniyor (PATH degil) ===
echo %ADB_EXE%
echo.
"%ADB_EXE%" version
if errorlevel 1 exit /b 1

echo.
echo === PATH teki ilk adb (farkliysa reverse hatasi normal) ===
where adb 2>nul
if errorlevel 1 echo (where adb: bulunamadi)
echo.

echo === reverse: telefon 127.0.0.1:8003 -^> PC 8003 ===
"%ADB_EXE%" reverse --remove tcp:8003 2>nul
"%ADB_EXE%" reverse tcp:8003 tcp:8003
if errorlevel 1 (
    echo [X] reverse basarisiz.
    exit /b 1
)
echo [OK] reverse aktif.
exit /b 0
