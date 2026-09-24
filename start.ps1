# SIH26085 Urban Flood Nowcasting System - PowerShell Launcher (Zero-Docker)
$ErrorActionPreference = "Stop"

$pyPath = "$env:LOCALAPPDATA\Programs\Python\Python311"
if (Test-Path $pyPath) {
    $env:PATH = "$pyPath;$pyPath\Scripts;$env:PATH"
}

Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "  SIH26085: High-Resolution Urban Flood Nowcasting System" -ForegroundColor Cyan
Write-Host "  Operating Mode: Standalone (Zero-Docker / Pure Local)" -ForegroundColor Green
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Select component to run:"
Write-Host "  [1] Start FastAPI Backend API (http://127.0.0.1:8000)"
Write-Host "  [2] Start Municipal Command Dashboard (http://localhost:3001)"
Write-Host "  [3] Start Citizen Emergency Portal (http://localhost:3000)"
Write-Host "  [4] Run All 45 Physics & Mass Balance Tests (pytest)"
Write-Host "  [5] Start All Services (API + Dashboard + Citizen Portal)"
Write-Host ""

$choice = Read-Host "Enter choice (1-5) [default 5]"
if (-not $choice) { $choice = "5" }

switch ($choice) {
    "1" {
        Write-Host "Starting FastAPI Backend..." -ForegroundColor Yellow
        python -m uvicorn services.api.main:app --host 127.0.0.1 --port 8000 --reload
    }
    "2" {
        Write-Host "Starting Municipal Dashboard on http://localhost:3001..." -ForegroundColor Yellow
        npm --prefix apps/city-dashboard run dev -- -p 3001
    }
    "3" {
        Write-Host "Starting Citizen Portal on http://localhost:3000..." -ForegroundColor Yellow
        npm --prefix apps/citizen-web run dev -- -p 3000
    }
    "4" {
        Write-Host "Running Physics and Integration Test Suite..." -ForegroundColor Yellow
        python -m pytest -v
    }
    "5" {
        Write-Host "Launching All 3 Services in separate terminal windows..." -ForegroundColor Green
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:PATH = '$pyPath;$pyPath\Scripts;' + `$env:PATH; cd '$PSScriptRoot'; python -m uvicorn services.api.main:app --host 127.0.0.1 --port 8000 --reload"
        Start-Sleep -Seconds 2
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; npm --prefix apps/city-dashboard run dev -- -p 3001"
        Start-Sleep -Seconds 1
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; npm --prefix apps/citizen-web run dev -- -p 3000"
        
        Write-Host "`nAll 3 services successfully launched!" -ForegroundColor Green
        Write-Host " - FastAPI Backend Docs:   http://127.0.0.1:8000/docs" -ForegroundColor Cyan
        Write-Host " - Citizen Portal:         http://localhost:3000" -ForegroundColor Cyan
        Write-Host " - Municipal Dashboard:    http://localhost:3001" -ForegroundColor Cyan
    }
}
