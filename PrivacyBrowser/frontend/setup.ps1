# setup.ps1
# ----------
# One-click setup for PrivacyBrowser frontend
# Run from: d:\broswer\PrivacyBrowser\frontend\

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║       PrivacyBrowser — Frontend Setup Script         ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$frontend = $PSScriptRoot

# ── Step 1: Check Python ─────────────────────────────────────────────────────
Write-Host "[1/4] Checking Python..." -ForegroundColor Yellow
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "❌ Python not found. Install from https://python.org" -ForegroundColor Red
    exit 1
}
$version = & python --version 2>&1
Write-Host "  ✅ $version found" -ForegroundColor Green

# ── Step 2: Create virtual environment ───────────────────────────────────────
Write-Host "[2/4] Creating virtual environment..." -ForegroundColor Yellow
$venvPath = Join-Path $frontend "venv"
if (-not (Test-Path $venvPath)) {
    python -m venv $venvPath
    Write-Host "  ✅ venv created at $venvPath" -ForegroundColor Green
} else {
    Write-Host "  ℹ️  venv already exists — skipping creation" -ForegroundColor Blue
}

# ── Step 3: Install dependencies ─────────────────────────────────────────────
Write-Host "[3/4] Installing Python packages (this may take a minute)..." -ForegroundColor Yellow
$pip = Join-Path $venvPath "Scripts\pip.exe"
& $pip install --upgrade pip -q
& $pip install -r (Join-Path $frontend "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ pip install failed." -ForegroundColor Red
    exit 1
}
Write-Host "  ✅ All packages installed." -ForegroundColor Green

# ── Step 4: Verify Go proxy binary ───────────────────────────────────────────
Write-Host "[4/4] Checking Go proxy binary..." -ForegroundColor Yellow
$goExe = Join-Path $frontend "..\backend\proxy_engine.exe"
if (Test-Path $goExe) {
    Write-Host "  ✅ proxy_engine.exe found: $goExe" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  proxy_engine.exe NOT found!" -ForegroundColor Red
    Write-Host "     To build it:" -ForegroundColor Yellow
    Write-Host '       $env:PATH = "C:\Program Files\Go\bin;" + $env:PATH' -ForegroundColor Gray
    Write-Host "       cd ..\backend" -ForegroundColor Gray
    Write-Host "       go build -o proxy_engine.exe ." -ForegroundColor Gray
}

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Setup complete! Launch the browser with:            ║" -ForegroundColor Cyan
Write-Host "║    .\venv\Scripts\python.exe main.py                 ║" -ForegroundColor White
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
