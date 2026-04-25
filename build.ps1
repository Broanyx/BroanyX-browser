# BroanyX Browser — Smart Build Script
# ======================================
# Usage:  .\build.ps1
#
# Builds BroanyX.exe with PyInstaller, then auto-detects which
# installer builder is available and uses it.
# Priority: Inno Setup > NSIS > pynsist > zip archive

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "   BroanyX Browser -- Build System" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Activate venv ────────────────────────────────────────────────────
$VenvPython  = Join-Path $ScriptDir "venv\Scripts\python.exe"
$VenvPip     = Join-Path $ScriptDir "venv\Scripts\pip.exe"
$VenvPyInst  = Join-Path $ScriptDir "venv\Scripts\pyinstaller.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "ERROR: venv not found. Run setup.ps1 first." -ForegroundColor Red
    exit 1
}

# ── Step 2: Install PyInstaller ──────────────────────────────────────────────
Write-Host "[1/4] Checking PyInstaller..." -ForegroundColor Yellow
& $VenvPython -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "      Installing PyInstaller..." -ForegroundColor Gray
    & $VenvPip install pyinstaller --quiet
}
Write-Host "      OK" -ForegroundColor Green

# ── Step 3: Clean and build ──────────────────────────────────────────────────
Write-Host "[2/4] Cleaning previous build..." -ForegroundColor Yellow
if (Test-Path "dist\BroanyX") { Remove-Item -Recurse -Force "dist\BroanyX" }
if (Test-Path "build")        { Remove-Item -Recurse -Force "build" }

Write-Host "[3/4] Building BroanyX.exe..." -ForegroundColor Yellow
Set-Location $ScriptDir
& $VenvPyInst broanyX.spec --clean --noconfirm --log-level WARN

if (-not (Test-Path "dist\BroanyX\BroanyX.exe")) {
    Write-Host "ERROR: PyInstaller build failed." -ForegroundColor Red
    exit 1
}
Copy-Item "version.json" "dist\BroanyX\version.json" -Force
Write-Host "      dist\BroanyX\BroanyX.exe -- OK" -ForegroundColor Green

# ── Step 4: Create installer ─────────────────────────────────────────────────
Write-Host "[4/4] Creating installer..." -ForegroundColor Yellow

# --- Option A: Inno Setup (preferred) ---
$InnoSetup = @(
    "C:\Users\LENOVO\AppData\Local\Programs\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 5\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($InnoSetup) {
    Write-Host "      Found Inno Setup -- building installer..." -ForegroundColor Gray
    & $InnoSetup "installer\BroanyX-InnoSetup.iss"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "      Installer: dist\BroanyX-Setup.exe" -ForegroundColor Green
        $installerBuilt = $true
    }
}

# --- Option B: NSIS ---
if (-not $installerBuilt) {
    $NSIS = @(
        "C:\Program Files (x86)\NSIS\makensis.exe",
        "C:\Program Files\NSIS\makensis.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($NSIS) {
        Write-Host "      Found NSIS -- building installer..." -ForegroundColor Gray
        & $NSIS "installer\BroanyX-Installer.nsi"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "      Installer: dist\BroanyX-Setup.exe" -ForegroundColor Green
            $installerBuilt = $true
        }
    }
}

# --- Option C: pynsist ---
if (-not $installerBuilt) {
    & $VenvPython -c "import nsist" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "      Found pynsist -- building installer..." -ForegroundColor Gray
        & $VenvPython -m nsist "installer\pynsist.cfg"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "      Installer created by pynsist" -ForegroundColor Green
            $installerBuilt = $true
        }
    }
}

# --- Option D: ZIP fallback ---
if (-not $installerBuilt) {
    Write-Host "      No installer tool found -- creating ZIP bundle instead..." -ForegroundColor Gray
    Compress-Archive -Path "dist\BroanyX\*" -DestinationPath "dist\BroanyX-portable.zip" -Force
    Write-Host "      Portable ZIP: dist\BroanyX-portable.zip" -ForegroundColor Green
    Write-Host ""
    Write-Host "  To create a proper installer, install one of:" -ForegroundColor Yellow
    Write-Host "  * Inno Setup (EASIEST): https://jrsoftware.org/isdl.php" -ForegroundColor White
    Write-Host "  * NSIS:                 https://nsis.sourceforge.io" -ForegroundColor White
    Write-Host "  * pynsist:              pip install pynsist" -ForegroundColor White
}

# ── Done ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host "  BUILD COMPLETE!" -ForegroundColor Green
Write-Host "  App:  dist\BroanyX\BroanyX.exe" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""
Write-Host "HOW TO RELEASE AN UPDATE:" -ForegroundColor Cyan
Write-Host "  1. Bump APP_VERSION in main.py + updater.py" -ForegroundColor White
Write-Host "  2. Run .\build.ps1" -ForegroundColor White
Write-Host "  3. Upload the installer .exe to GitHub Releases" -ForegroundColor White
Write-Host "  4. Edit version.json on GitHub with the new version number" -ForegroundColor White
Write-Host "  -> Every installed copy will see the update on next launch!" -ForegroundColor Green
Write-Host ""
