@echo off
setlocal
title Ember AI Launcher
color 0D
cd /d "%~dp0"

echo =========================================
echo       Waking up Ember's Systems...
echo =========================================
echo.

set SOVITS_PATH=C:\Users\hemaf\Desktop\GPT-SoVITS-v3lora-20250228\GPT-SoVITS-v3lora-20250228

if not exist ".venv\Scripts\activate" (
    echo [ERROR] .venv was not found in this folder.
    echo Create it first: python -m venv .venv
    pause
    exit /b 1
)

echo [1] Starting GPT-SoVITS API...
start "GPT-SoVITS API" cmd /k "cd /d %SOVITS_PATH% && runtime\python.exe api_v2.py"

set MAX_WAIT=120
set WAITED=0
echo Waiting for GPT-SoVITS on 127.0.0.1:9880...

:wait_sovits
powershell -NoProfile -Command "try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',9880); $c.Close(); exit 0 } catch { exit 1 }" >NUL 2>&1
if %errorlevel%==0 goto sovits_ready

if %WAITED% GEQ %MAX_WAIT% (
    echo [ERROR] GPT-SoVITS did not become ready within %MAX_WAIT% seconds.
    echo Check GPT-SoVITS window for errors.
    pause
    exit /b 1
)

set /a WAITED+=1
timeout /t 1 /nobreak > NUL
goto wait_sovits

:sovits_ready
echo GPT-SoVITS is ready.

echo [2] Starting Ember TTS Proxy...
start "Ember TTS Proxy" cmd /k "cd /d ""%~dp0"" && call .venv\Scripts\activate && python tts_server.py"

set WAITED=0
echo Waiting for Ember TTS proxy on 127.0.0.1:5050...

:wait_proxy
powershell -NoProfile -Command "try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',5050); $c.Close(); exit 0 } catch { exit 1 }" >NUL 2>&1
if %errorlevel%==0 goto proxy_ready
if %WAITED% GEQ %MAX_WAIT% (
    echo [ERROR] Ember TTS proxy did not become ready within %MAX_WAIT% seconds.
    echo Check tts_server.py window for errors.
    pause
    exit /b 1
)
set /a WAITED+=1
timeout /t 1 /nobreak > NUL
goto wait_proxy

:proxy_ready
echo TTS proxy is ready.

echo [3] Starting Ember Backend...
start "Ember Backend" cmd /k "cd /d ""%~dp0"" && call .venv\Scripts\activate && python app.py"

echo.
echo ✅ All systems are online, Ebrahim! You can close this small window now.
pause
