@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title REG-01 Auto Installer and Launcher

set "SCRIPT_PATH=%~f0"
set "ROOT_DIR=%~dp0"
if not exist "%ROOT_DIR%backend\" (
    for %%I in ("%ROOT_DIR%..") do set "ROOT_DIR=%%~fI\"
)
cd /d "%ROOT_DIR%"
set "ROOT_DIR=%CD%"
set "ENV_FILE=%ROOT_DIR%\backend\.env"
set "ENV_EXAMPLE=%ROOT_DIR%\backend\.env.example"
set "MODE=install"
if /I "%~1"=="start" set "MODE=start"
if /I "%~1"=="--start" set "MODE=start"
if /I "%~1"=="install" set "MODE=install"
if /I "%~1"=="--install" set "MODE=install"

call :print_header

if /I "%MODE%"=="start" goto :start_mode

call :ensure_admin
if "%errorlevel%"=="100" exit /b 0
if not "%errorlevel%"=="0" goto :fatal

call :ensure_winget || goto :fatal
call :ensure_wsl || goto :fatal
call :ensure_python || goto :fatal
call :ensure_docker_installed || goto :fatal
call :ensure_env_file || goto :fatal
call :ensure_docker_engine || goto :fatal
call :ensure_docker_login || goto :fatal
call :start_services || goto :fatal

echo.
echo [DONE] REG-01 is ready.
echo        Frontend: http://localhost:3000
echo        Backend : http://localhost:5000
echo.
echo Keep Docker Desktop running while using the system.
exit /b 0

:start_mode
call :check_docker_cli || goto :fatal
call :ensure_env_file || goto :fatal
call :ensure_docker_engine || goto :fatal
call :start_services || goto :fatal
echo.
echo [DONE] REG-01 is running.
echo        Frontend: http://localhost:3000
echo        Backend : http://localhost:5000
echo.
echo Keep Docker Desktop running while using the system.
exit /b 0

:fatal
echo.
echo [ERROR] Setup did not complete.
echo         Fix the issue above, then run this script again.
exit /b 1

:print_header
echo ============================================================
echo REG-01 Automated Bootstrap (Windows)
echo ============================================================
if /I "%MODE%"=="start" goto :print_header_start

echo Mode: INSTALL ^(install missing dependencies, then launch^)
echo ============================================================
echo This mode will:
echo   1^) Check and install WSL, Python 3.11, Docker Desktop
echo   2^) Ask for manual steps only when truly required
echo   3^) Re-check every manual step before continuing
echo   4^) Launch the stack with docker compose
echo ============================================================
echo.
exit /b 0

:print_header_start
echo Mode: START ^(check Docker readiness and launch services^)
echo ============================================================
echo This mode will:
echo   1^) Check Docker CLI, Docker Engine, and compose
echo   2^) Validate backend\.env before startup
echo   3^) Launch the stack with docker compose
echo ============================================================
echo.
exit /b 0

:ensure_admin
net session >nul 2>&1
if not errorlevel 1 (
    echo [OK] Administrator privileges confirmed.
    exit /b 0
)

echo [INFO] Administrator rights are required. Relaunching...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%SCRIPT_PATH%' -WorkingDirectory '%ROOT_DIR%' -Verb RunAs"
if errorlevel 1 (
    echo [ERROR] Could not relaunch with administrator privileges.
    exit /b 1
)
echo [INFO] Elevated window opened. Closing current window.
exit /b 100

:ensure_winget
where winget >nul 2>&1
if not errorlevel 1 (
    echo [OK] winget is available.
    exit /b 0
)

echo [MANUAL STEP] winget is missing.
echo              Install "App Installer" from Microsoft Store.
start "" "ms-windows-store://pdp/?ProductId=9NBLGGH4NNS1"
call :wait_for_yes "Type Y after winget is installed: "

where winget >nul 2>&1
if not errorlevel 1 (
    echo [OK] winget is now available.
    exit /b 0
)

echo [ERROR] winget is still not available.
exit /b 1

:ensure_wsl
wsl --status >nul 2>&1
if not errorlevel 1 (
    wsl --set-default-version 2 >nul 2>&1
    echo [OK] WSL is ready.
    exit /b 0
)

echo [INFO] Installing WSL...
winget install -e --id Microsoft.WSL --accept-package-agreements --accept-source-agreements >nul 2>&1
wsl --install --no-distribution >nul 2>&1
if errorlevel 1 wsl --install >nul 2>&1
wsl --set-default-version 2 >nul 2>&1

timeout /t 5 >nul
wsl --status >nul 2>&1
if not errorlevel 1 (
    echo [OK] WSL installed successfully.
    exit /b 0
)

echo [MANUAL STEP] WSL installation may require a Windows restart.
echo              1) Restart Windows
echo              2) Re-open this script as Administrator
call :wait_for_yes "Type Y to re-check WSL now (after completing the step): "

wsl --status >nul 2>&1
if not errorlevel 1 (
    echo [OK] WSL is now ready.
    exit /b 0
)

echo [ERROR] WSL is still not ready.
exit /b 1

:ensure_python
call :has_python_311
if not errorlevel 1 (
    echo [OK] Python 3.11+ is ready.
    exit /b 0
)

echo [INFO] Installing Python 3.11...
winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements --scope machine >nul 2>&1

call :has_python_311
if not errorlevel 1 (
    echo [OK] Python 3.11+ installed.
    exit /b 0
)

echo [ERROR] Python 3.11+ is still not available.
echo         Please install Python 3.11 manually, then run this script again.
exit /b 1

:has_python_311
py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if not errorlevel 1 exit /b 0

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if not errorlevel 1 exit /b 0

exit /b 1

:check_docker_cli
docker --version >nul 2>&1
if not errorlevel 1 goto :docker_cli_present

if exist "%ProgramFiles%\Docker\Docker\resources\bin\docker.exe" (
    set "PATH=%ProgramFiles%\Docker\Docker\resources\bin;%PATH%"
)
if exist "%LocalAppData%\Programs\Docker\Docker\resources\bin\docker.exe" (
    set "PATH=%LocalAppData%\Programs\Docker\Docker\resources\bin;%PATH%"
)

docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker CLI not found.
    echo         Run install mode first: install\setup_auto.bat
    exit /b 1
)

:docker_cli_present
docker compose version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] docker compose is not available.
    echo         Reinstall Docker Desktop or run install mode first.
    exit /b 1
)

echo [OK] Docker CLI + Compose are ready.
exit /b 0

:ensure_docker_installed
docker --version >nul 2>&1
if not errorlevel 1 goto :docker_cli_ok

if exist "%ProgramFiles%\Docker\Docker\resources\bin\docker.exe" (
    set "PATH=%ProgramFiles%\Docker\Docker\resources\bin;%PATH%"
)
if exist "%LocalAppData%\Programs\Docker\Docker\resources\bin\docker.exe" (
    set "PATH=%LocalAppData%\Programs\Docker\Docker\resources\bin;%PATH%"
)

docker --version >nul 2>&1
if not errorlevel 1 goto :docker_cli_ok

echo [INFO] Installing Docker Desktop...
winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements >nul 2>&1

if exist "%ProgramFiles%\Docker\Docker\resources\bin\docker.exe" (
    set "PATH=%ProgramFiles%\Docker\Docker\resources\bin;%PATH%"
)
if exist "%LocalAppData%\Programs\Docker\Docker\resources\bin\docker.exe" (
    set "PATH=%LocalAppData%\Programs\Docker\Docker\resources\bin;%PATH%"
)

docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker CLI is still not available.
    exit /b 1
)

:docker_cli_ok
docker compose version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] docker compose is not available.
    echo         Reinstall Docker Desktop, then run this script again.
    exit /b 1
)

echo [OK] Docker CLI + Compose are ready.
exit /b 0

:ensure_env_file
if not exist "%ENV_FILE%" (
    if not exist "%ENV_EXAMPLE%" (
        echo [ERROR] Missing %ENV_EXAMPLE%
        exit /b 1
    )
    copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
    echo [INFO] Created backend\.env from backend\.env.example
)

:env_validate_loop
call :validate_env
set "ENV_STATUS=%errorlevel%"
if "%ENV_STATUS%"=="0" (
    echo [OK] backend\.env passed validation.
    exit /b 0
)

echo [MANUAL STEP] backend\.env needs updates:
if "%ENV_STATUS%"=="1" echo              - backend\.env does not exist.
if "%ENV_STATUS%"=="2" echo              - LLM_PROVIDER is empty.
if "%ENV_STATUS%"=="3" echo              - OPENAI_API_KEY is empty while LLM_PROVIDER=openai.
if "%ENV_STATUS%"=="4" echo              - GEMINI_API_KEY is empty while LLM_PROVIDER=gemini.
if "%ENV_STATUS%"=="5" echo              - LLM_PROVIDER must be one of: openai, gemini, local.

start "" notepad "%ENV_FILE%"
call :wait_for_yes "Type Y after saving backend\\.env: "
goto :env_validate_loop

:validate_env
if not exist "%ENV_FILE%" exit /b 1

set "LLM_PROVIDER="
for /f "tokens=1,* delims==" %%A in ('findstr /B /I "LLM_PROVIDER=" "%ENV_FILE%"') do (
    if /I "%%A"=="LLM_PROVIDER" set "LLM_PROVIDER=%%B"
)

if not defined LLM_PROVIDER exit /b 2

if /I "!LLM_PROVIDER!"=="openai" (
    findstr /R /B /C:"OPENAI_API_KEY=[^ #]" "%ENV_FILE%" >nul
    if errorlevel 1 exit /b 3
    exit /b 0
)

if /I "!LLM_PROVIDER!"=="gemini" (
    findstr /R /B /C:"GEMINI_API_KEY=[^ #]" "%ENV_FILE%" >nul
    if errorlevel 1 exit /b 4
    exit /b 0
)

if /I "!LLM_PROVIDER!"=="local" exit /b 0

exit /b 5

:ensure_docker_engine
docker info >nul 2>&1
if not errorlevel 1 (
    echo [OK] Docker engine is running.
    exit /b 0
)

echo [INFO] Starting Docker Desktop...
if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
    start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
)
if exist "%LocalAppData%\Programs\Docker\Docker\Docker Desktop.exe" (
    start "" "%LocalAppData%\Programs\Docker\Docker\Docker Desktop.exe"
)

echo [INFO] Waiting for Docker engine...
for /l %%I in (1,1,60) do (
    docker info >nul 2>&1
    if not errorlevel 1 (
        echo [OK] Docker engine is running.
        exit /b 0
    )
    timeout /t 5 >nul
)

echo [MANUAL STEP] Open Docker Desktop and wait until Engine status is running.
call :wait_for_yes "Type Y after Docker Desktop is fully ready: "

docker info >nul 2>&1
if not errorlevel 1 (
    echo [OK] Docker engine is running.
    exit /b 0
)

echo [ERROR] Docker engine is still not ready.
exit /b 1

:ensure_docker_login
docker info --format "{{.Username}}" >nul 2>&1
if errorlevel 1 (
    if exist "%USERPROFILE%\.docker\config.json" (
        findstr /R /C:"\"auth\"[ ]*:[ ]*\"[^\"]\"" "%USERPROFILE%\.docker\config.json" >nul
        if not errorlevel 1 (
            echo [OK] Docker credentials found in config.json.
            exit /b 0
        )
    )
    echo [WARN] Docker login status cannot be verified automatically on this Docker version.
    echo        Continuing without login verification.
    exit /b 0
)

set "DOCKER_USER="
for /f "usebackq delims=" %%U in (`docker info --format "{{.Username}}" 2^>nul`) do set "DOCKER_USER=%%U"

if defined DOCKER_USER (
    if /I not "!DOCKER_USER!"=="<no value>" (
        echo [OK] Docker is logged in as !DOCKER_USER!.
        exit /b 0
    )
)

echo [MANUAL STEP] Docker login is required.
echo              A terminal will open for: docker login
start "Docker Login" cmd /k "docker login"
call :wait_for_yes "Type Y after docker login is completed: "

set "DOCKER_USER="
for /f "usebackq delims=" %%U in (`docker info --format "{{.Username}}" 2^>nul`) do set "DOCKER_USER=%%U"
if defined DOCKER_USER (
    if /I not "!DOCKER_USER!"=="<no value>" (
        echo [OK] Docker login verified for !DOCKER_USER!.
        exit /b 0
    )
)

echo [ERROR] Docker login is still not verified.
exit /b 1

:start_services
echo [INFO] Cleaning stale compose resources...
docker compose down --remove-orphans >nul 2>&1

echo [INFO] Starting REG-01 services with docker compose...
docker compose up -d --build
if errorlevel 1 (
    echo [ERROR] docker compose up failed.
    exit /b 1
)

echo [INFO] Waiting for backend to respond on http://localhost:5000 ...
set "BACKEND_READY=0"
set "HAS_CURL=0"
where curl.exe >nul 2>&1
if not errorlevel 1 set "HAS_CURL=1"
for /l %%I in (1,1,80) do (
    if "!HAS_CURL!"=="1" (
        curl.exe --silent --show-error --fail --max-time 5 http://localhost:5000/ >nul 2>&1
    ) else (
        powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'http://localhost:5000/' -UseBasicParsing -TimeoutSec 5 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
    )
    if not errorlevel 1 (
        set "BACKEND_READY=1"
        goto :backend_ready
    )
    timeout /t 3 >nul
)

:backend_ready
if "!BACKEND_READY!"=="1" (
    echo [OK] Backend is reachable.
) else (
    echo [WARN] Backend did not respond in time.
    echo        Check logs with: docker compose logs backend --tail 200
)

echo [INFO] Current container status:
docker compose ps

start "" "http://localhost:3000"
exit /b 0

:wait_for_yes
set "PROMPT=%~1"
:wait_for_yes_loop
set "ANSWER="
set /p ANSWER=%PROMPT%
if /I "!ANSWER!"=="Y" exit /b 0
if /I "!ANSWER!"=="YES" exit /b 0
echo Please type Y when done.
goto :wait_for_yes_loop
