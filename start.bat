@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo [House-Telecom] Starting setup and launch...

if not exist ".venv\Scripts\python.exe" (
    echo [1/5] Creating Python virtual environment .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create .venv. Please ensure Python 3.11+ is installed.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -c "import fastapi, uvicorn, sqlalchemy" >nul 2>&1
if errorlevel 1 (
    echo [2/5] Installing Python dependencies...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -e .
    if errorlevel 1 (
        echo [ERROR] Failed to install Python dependencies.
        pause
        exit /b 1
    )
) else (
    echo [2/5] Python dependencies already installed.
)

if not exist ".env" (
    if exist ".env.example" (
        echo [3/5] Copying .env.example to .env...
        copy /y ".env.example" ".env" >nul
    )
) else (
    echo [3/5] .env already exists.
)

if not exist "frontend\node_modules" (
    echo [4/5] Installing frontend dependencies...
    pushd frontend
    call npm.cmd install
    if errorlevel 1 (
        popd
        echo [ERROR] Failed to install frontend dependencies.
        pause
        exit /b 1
    )
    popd
) else (
    echo [4/5] Frontend node_modules already installed.
)

echo [5/5] Starting Backend (127.0.0.1:8001) and Frontend (localhost:4002)...
start "House-Telecom Backend" cmd /k "cd /d "%~dp0" && ".venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001"
start "House-Telecom Frontend" cmd /k "cd /d "%~dp0frontend" && npm.cmd run dev -- --port 4002"

timeout /t 3 /nobreak >nul
start "" "http://localhost:4002"

echo [House-Telecom] Launched! Close the Backend/Frontend windows to stop the servers.
endlocal
