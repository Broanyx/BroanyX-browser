# BroanyX Browser — One-Click Setup Script
# Run this from the d:\broswer directory in PowerShell

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   BroanyX Browser Setup" -ForegroundColor Cyan  
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "[1/4] Checking Python..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "  Found: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Python not found. Install from https://python.org" -ForegroundColor Red
    exit 1
}

# Create virtual environment
Write-Host ""
Write-Host "[2/4] Creating virtual environment..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "  venv already exists — skipping creation." -ForegroundColor Gray
} else {
    python -m venv venv
    Write-Host "  Virtual environment created." -ForegroundColor Green
}

# Activate venv
Write-Host ""
Write-Host "[3/4] Installing dependencies..." -ForegroundColor Yellow
Write-Host "  (This may take a few minutes for PyQt6-WebEngine)" -ForegroundColor Gray
& ".\venv\Scripts\pip.exe" install --upgrade pip --quiet
& ".\venv\Scripts\pip.exe" install -r requirements.txt

Write-Host ""
Write-Host "[4/4] Verifying installation..." -ForegroundColor Yellow
$result = & ".\venv\Scripts\python.exe" -c "
import PyQt6
import PyQt6.QtWebEngineWidgets
print('PyQt6 OK')
import stem
print('stem OK')
import adblockparser
print('adblockparser OK')
import requests
print('requests OK')
print('ALL DEPENDENCIES OK')
" 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host $result -ForegroundColor Green
} else {
    Write-Host "  Some packages failed. See error above." -ForegroundColor Red
    Write-Host $result
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  To launch BroanyX Browser:" -ForegroundColor White
Write-Host "  > .\venv\Scripts\python.exe main.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "  NOTE: Install Tor from https://www.torproject.org/download/" -ForegroundColor Yellow
Write-Host "  and ensure tor.exe is in your PATH for Tor features." -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
