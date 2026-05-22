@echo off
setlocal EnableExtensions

rem flutter run oncesi adb reverse
set "ADB_EXE="
if defined ANDROID_HOME if exist "%ANDROID_HOME%\platform-tools\adb.exe" (
    set "ADB_EXE=%ANDROID_HOME%\platform-tools\adb.exe"
)
if not defined ADB_EXE if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" (
    set "ADB_EXE=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
)
if not defined ADB_EXE set "ADB_EXE=adb"

echo [1/2] ADB reverse: telefon tcp:8003 ^> bilgisayar tcp:8003
"%ADB_EXE%" reverse --remove tcp:8003 2>nul
"%ADB_EXE%" reverse tcp:8003 tcp:8003
if errorlevel 1 (
    echo [UYARI] ADB reverse basarisiz. USB kablosu ve hata ayiklamayi kontrol edin.
) else (
    echo [OK] ADB reverse aktif (port 8003).
)

echo [2/2] Flutter baslatiliyor...
flutter run
