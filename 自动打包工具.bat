@echo off
setlocal
cd /d "%~dp0"

title ColorCard Portable Build

set "SOURCE_FILE=%~1"
if "%SOURCE_FILE%"=="" set "SOURCE_FILE=ColorCard.py"

for %%i in ("%SOURCE_FILE%") do (
    set "SOURCE_PATH=%%~fi"
    set "TOOL_NAME=%%~ni"
)

if not exist "%SOURCE_PATH%" (
    echo [ERROR] Source file not found: %SOURCE_PATH%
    if "%~1"=="" pause
    exit /b 1
)

set "OUT_FOLDER=%~dp0%TOOL_NAME%-Windows"
set "BUILD_ROOT=%~dp0.build_%TOOL_NAME%"
set "VENV_FOLDER=%BUILD_ROOT%\venv"
set "STAGING_FOLDER=%BUILD_ROOT%\dist"
set "DIST_NAME=%TOOL_NAME%-portable"
set "ORIGINAL_TEMP=%TEMP%"
set "ORIGINAL_TMP=%TMP%"
set "TEMP=%BUILD_ROOT%\temp"
set "TMP=%BUILD_ROOT%\temp"
if not exist "%TEMP%" mkdir "%TEMP%"

echo =========================================
echo   Building: %DIST_NAME%.exe
echo =========================================

if not exist "%VENV_FOLDER%\Scripts\pip.exe" (
    echo [1/4] Creating build environment...
    if exist "%VENV_FOLDER%" rmdir /s /q "%VENV_FOLDER%"
    python -m venv "%VENV_FOLDER%"
    if errorlevel 1 goto :build_failed
) else (
    echo [1/4] Reusing build environment...
)

echo [2/4] Checking build dependencies...
call "%VENV_FOLDER%\Scripts\activate.bat"
python -m pip install --upgrade pip -q
python -m pip install -r "%~dp0requirements.txt" pyinstaller -q
if errorlevel 1 goto :build_failed_active

echo [3/4] Preparing staging output...
if exist "%BUILD_ROOT%\work" rmdir /s /q "%BUILD_ROOT%\work"
if exist "%STAGING_FOLDER%" rmdir /s /q "%STAGING_FOLDER%"
mkdir "%STAGING_FOLDER%"

echo [4/4] Creating one-file executable...
python -m PyInstaller --onefile --windowed --noconfirm --clean ^
    --name "%DIST_NAME%" ^
    --distpath "%STAGING_FOLDER%" ^
    --workpath "%BUILD_ROOT%\work" ^
    --specpath "%BUILD_ROOT%" ^
    "%SOURCE_PATH%"
if errorlevel 1 goto :build_failed_active

if exist "%OUT_FOLDER%" rmdir /s /q "%OUT_FOLDER%"
move "%STAGING_FOLDER%" "%OUT_FOLDER%" >nul
if errorlevel 1 goto :build_failed_active

call deactivate
set "TEMP=%ORIGINAL_TEMP%"
set "TMP=%ORIGINAL_TMP%"
rmdir /s /q "%BUILD_ROOT%" 2>nul

if not exist "%OUT_FOLDER%\%DIST_NAME%.exe" goto :build_failed

echo.
echo =========================================
echo   Build complete:
echo   %OUT_FOLDER%\%DIST_NAME%.exe
echo =========================================
if "%~1"=="" pause
exit /b 0

:build_failed_active
call deactivate

:build_failed
set "TEMP=%ORIGINAL_TEMP%"
set "TMP=%ORIGINAL_TMP%"
rmdir /s /q "%BUILD_ROOT%" 2>nul
echo.
echo [ERROR] Build failed. Check the log above.
if "%~1"=="" pause
exit /b 1
