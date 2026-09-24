@echo off
setlocal
cd /d "%~dp0"
set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"

echo ====================================================================
echo   SIH26085: High-Resolution Urban Flood Nowcasting System
echo   Operating Mode: Standalone (Zero-Docker / Pure Local)
echo ====================================================================
echo.
echo Select component to run:
echo   [1] Start FastAPI Backend API (http://127.0.0.1:8000)
echo   [2] Start Municipal Command Dashboard (http://localhost:3001)
echo   [3] Start Citizen Emergency Portal (http://localhost:3000)
echo   [4] Run All 45 Physics & Mass Balance Tests (pytest)
echo   [5] Start All Services Simultaneously
echo.
set /p choice="Enter choice (1-5) [default 5]: "
if "%choice%"=="" set choice=5

if "%choice%"=="1" goto run_api
if "%choice%"=="2" goto run_dash
if "%choice%"=="3" goto run_citizen
if "%choice%"=="4" goto run_test
if "%choice%"=="5" goto run_all
goto run_all

:run_api
echo Starting FastAPI Backend...
python -m uvicorn services.api.main:app --host 127.0.0.1 --port 8000 --reload
goto end

:run_dash
echo Starting Municipal Dashboard on http://localhost:3001...
npm --prefix apps/city-dashboard run dev -- -p 3001
goto end

:run_citizen
echo Starting Citizen Portal on http://localhost:3000...
npm --prefix apps/citizen-web run dev -- -p 3000
goto end

:run_test
echo Running Physics and Integration Test Suite...
python -m pytest -v
goto end

:run_all
echo Starting Backend API in new window...
start "SIH26085 - FastAPI Backend (Port 8000)" cmd /k "cd /d %~dp0 && python -m uvicorn services.api.main:app --host 127.0.0.1 --port 8000 --reload"
timeout /t 2 /nobreak >nul

echo Starting Municipal Dashboard in new window...
start "SIH26085 - Municipal Dashboard (Port 3001)" cmd /k "cd /d %~dp0 && npm --prefix apps/city-dashboard run dev -- -p 3001"
timeout /t 1 /nobreak >nul

echo Starting Citizen Portal in new window...
start "SIH26085 - Citizen Portal (Port 3000)" cmd /k "cd /d %~dp0 && npm --prefix apps/citizen-web run dev -- -p 3000"

echo.
echo All 3 services launched in separate windows!
echo - FastAPI Docs:         http://127.0.0.1:8000/docs
echo - Citizen Portal:       http://localhost:3000
echo - Municipal Dashboard:  http://localhost:3001
echo.
goto end

:end
pause
