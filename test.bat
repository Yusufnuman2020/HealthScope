@echo off
chcp 65001 >nul
title HealthScope Test ve Dogruluk Olcumu
cd /d "%~dp0"

echo.
echo  ===============================================
echo    HealthScope - Test ve Dogruluk Olcumu
echo  ===============================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo  [HATA] Sanal ortam bulunamadi: .venv
    echo         Once kurulum yapin:  py -3.14 -m venv .venv
    echo.
    pause
    exit /b 1
)

set PY=.venv\Scripts\python.exe
set FAILED=0

echo  --------------------------------------------------
echo   [1/4] Vaka havuzu dogrulamasi
echo  --------------------------------------------------
%PY% -X utf8 scripts\build_presets.py --check
if errorlevel 1 (
    echo  ^>^> BASARISIZ
    set FAILED=1
) else (
    echo  ^>^> OK
)
echo.

echo  --------------------------------------------------
echo   [2/4] Birim testleri ^(pytest^)
echo  --------------------------------------------------
%PY% -X utf8 -m pytest tests -q
if errorlevel 1 (
    echo  ^>^> BASARISIZ
    set FAILED=1
) else (
    echo  ^>^> OK
)
echo.

echo  --------------------------------------------------
echo   [3/4] Dogruluk olcumu - deterministik katmanlar
echo  --------------------------------------------------
%PY% -X utf8 scripts\evaluate.py --offline
echo.

echo  --------------------------------------------------
echo   [4/4] Dogruluk olcumu - dil modeli katmani
echo  --------------------------------------------------
REM Bu asama calisan bir backend gerektirir. Yoksa atlanir.
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    echo  [ATLANDI] Port 8000'de calisan bir sunucu yok.
    echo            Dil modeli katmanini da olcmek icin once baslat.bat calistirin,
    echo            "BERTurk hazir" yazisini bekleyin, sonra bu testi tekrar acin.
) else (
    echo  Sunucu bulundu, 118 vaka calistiriliyor ^(birkac dakika surebilir^)...
    echo.
    %PY% -X utf8 scripts\evaluate.py
)

echo.
echo  ===============================================
if %FAILED%==1 (
    echo    SONUC: BAZI TESTLER BASARISIZ
) else (
    echo    SONUC: TUM TESTLER GECTI
)
echo  ===============================================
echo.
pause
