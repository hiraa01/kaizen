@echo off
setlocal EnableExtensions
rem Prints SHA-1 / SHA-256 for each build variant (use for Google Cloud Android OAuth client).
rem Gradle needs Java 11+. If this fails, install Android Studio or set JAVA_HOME to JDK 17+.

set "JBR=%ProgramFiles%\Android\Android Studio\jbr"
if not exist "%JBR%\bin\java.exe" set "JBR=%LocalAppData%\Android\Android Studio\jbr"
if not exist "%JBR%\bin\java.exe" set "JBR=%ProgramFiles%\Android\Android Studio\jbr\Contents\Home"

if exist "%JBR%\bin\java.exe" (
  set "JAVA_HOME=%JBR%"
  set "PATH=%JAVA_HOME%\bin;%PATH%"
  echo Using JAVA_HOME=%JAVA_HOME%
  "%JAVA_HOME%\bin\java.exe" -version 2>&1
) else (
  echo [!] Android Studio JBR not found. Set JAVA_HOME to JDK 17+ then run again.
  echo     Tried: %%ProgramFiles%%\Android\Android Studio\jbr
  echo     Tried: %%LocalAppData%%\Android\Android Studio\jbr
)

cd /d "%~dp0"
call gradlew.bat signingReport --no-daemon
echo.
echo --- Next step ---
echo In Google Cloud Console - Credentials - OAuth 2.0 Client ID (Android):
echo   Package name: com.example.osym_rehberi
echo   Add SHA-1 from "Variant: debug" / Config: debug above (for flutter run).
echo   Web client ID in GOOGLE_SERVER_CLIENT_ID must be in the SAME GCP project.
pause
