@echo off
chcp 65001 >nul
title HealthScope Baslatici
cd /d "%~dp0"

echo.
echo  ===============================================
echo    HealthScope - Klinik Karar Destek Sistemi
echo  ===============================================
echo.

REM --- Onkosullari dogrula: eksikse sessizce yarim acilmasin ---
if not exist ".venv\Scripts\activate.bat" (
    echo  [HATA] Sanal ortam bulunamadi: .venv
    echo.
    echo  Once kurulumu yapin:
    echo      py -3.14 -m venv .venv
    echo      .venv\Scripts\activate.bat
    echo      pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

if not exist "node_modules" (
    echo  [HATA] node_modules bulunamadi.
    echo.
    echo  Once calistirin:  npm install
    echo.
    pause
    exit /b 1
)

if not exist ".env" (
    echo  [UYARI] .env dosyasi yok. Model yolu tanimli olmayabilir.
    echo          .env.example dosyasini .env olarak kopyalayip duzenleyin.
    echo.
)

REM --- Port 8000 zaten dolu mu? Eski bir sunucu artigi kafa karistirir. ---
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo  [UYARI] Port 8000 zaten kullanimda - eski bir sunucu calisiyor olabilir.
    echo          Arayuz o sunucuya baglanir. Kapatmak icin:
    echo.
    netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"
    echo.
    echo          taskkill /PID ^<PID^> /T /F
    echo.
    choice /C DK /N /M "  [D]evam et  /  [K]apat: "
    if errorlevel 2 exit /b 0
)

echo  [1/2] Yapay zeka sunucusu baslatiliyor (port 8000)...
start "HealthScope API - kapatmak icin Ctrl+C" cmd /k "cd /d "%~dp0" && call .venv\Scripts\activate.bat && python api_server.py"

echo  [2/2] Arayuz baslatiliyor (port 3000)...
start "HealthScope Web - kapatmak icin Ctrl+C" cmd /k "cd /d "%~dp0" && npm run dev"

echo.
echo  Model yuklenirken 10-30 saniye surebilir.
echo  API penceresinde "BERTurk hazir" yazisini bekleyin.
echo.

REM --- Arayuz ayaga kalkinca tarayiciyi ac (en fazla ~40 sn bekle) ---
echo  Arayuzun hazir olmasi bekleniyor...
set /a _tries=0
:wait_web
set /a _tries+=1
timeout /t 2 /nobreak >nul
netstat -ano | findstr ":3000" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    if %_tries% lss 20 goto wait_web
    echo  [UYARI] Arayuz 40 saniyede acilmadi. Web penceresini kontrol edin.
    goto done
)

start "" "http://localhost:3000/HealthScope"
echo  Tarayici acildi: http://localhost:3000/HealthScope

:done
echo.
echo  Iki pencereyi de Ctrl+C ile kapatin (carpi ile kapatmayin:
echo  arka planda surec kalip port 8000'i tutabilir).
echo.
timeout /t 8 /nobreak >nul
