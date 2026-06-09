@echo off
REM ===========================================================================
REM  Qwen3-TTS Studio - one-click launcher (Windows)
REM
REM  Starts the API server (GPU-resident models) in its own window, waits for
REM  it to become healthy, then starts the Web UI (thin client) and opens the
REM  browser. Other apps on this PC can also call the API at QWEN_TTS_API_URL.
REM
REM  Edit the variables below if you use a different venv path or ports.
REM ===========================================================================
setlocal

REM --- Configuration ---------------------------------------------------------
set "REPO_DIR=%~dp0"
set "VENV_ACTIVATE=%REPO_DIR%.venv\Scripts\activate.bat"
set "API_HOST=127.0.0.1"
set "API_PORT=8001"
set "API_URL=http://%API_HOST%:%API_PORT%"

REM --- Activate virtual environment ------------------------------------------
if not exist "%VENV_ACTIVATE%" (
  echo [ERROR] venv not found at "%VENV_ACTIVATE%"
  echo         Create it first:  uv sync
  pause
  exit /b 1
)
call "%VENV_ACTIVATE%"

REM --- 1) Start the API server in a separate window --------------------------
echo [Qwen3-TTS] Starting API server on %API_URL% ...
set "QWEN_TTS_HOST=%API_HOST%"
set "QWEN_TTS_PORT=%API_PORT%"
start "Qwen3-TTS API" cmd /k "call ""%VENV_ACTIVATE%"" && python ""%REPO_DIR%server\tts_server_async.py"""

REM --- 2) Wait until the API server is healthy --------------------------------
echo [Qwen3-TTS] Waiting for the API server to load models...
set /a TRIES=0
:WAIT_LOOP
set /a TRIES+=1
powershell -NoProfile -Command "try { Invoke-RestMethod -Uri '%API_URL%/health' -TimeoutSec 3 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL%==0 goto API_READY
if %TRIES% GEQ 120 (
  echo [ERROR] API server did not become healthy in time. Check its window.
  pause
  exit /b 1
)
timeout /t 2 /nobreak >nul
goto WAIT_LOOP

:API_READY
echo [Qwen3-TTS] API server is ready.

REM --- 3) Start the Web UI (opens the browser automatically) ------------------
echo [Qwen3-TTS] Starting Web UI...
set "QWEN_TTS_API_URL=%API_URL%"
python "%REPO_DIR%ui\launch_ui.py"

endlocal
