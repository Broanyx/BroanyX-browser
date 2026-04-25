# create_shortcut.ps1
# ====================
# Creates a Desktop shortcut to launch BroanyX Browser from source
# (for development — run this once to pin the browser to your desktop)
#
# Usage: .\create_shortcut.ps1

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python     = Join-Path $ScriptDir "venv\Scripts\pythonw.exe"   # pythonw = no console
$MainScript = Join-Path $ScriptDir "main.py"
$IconFile   = Join-Path $ScriptDir "assets\icon.ico"
$Desktop    = [System.Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "BroanyX Browser.lnk"

# Check pythonw.exe exists
if (-not (Test-Path $Python)) {
    Write-Host "ERROR: pythonw.exe not found at $Python" -ForegroundColor Red
    Write-Host "Make sure your venv is set up: python -m venv venv && .\venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

# Create the shortcut
$WScriptShell = New-Object -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath       = $Python
$Shortcut.Arguments        = "`"$MainScript`""
$Shortcut.WorkingDirectory = $ScriptDir
$Shortcut.IconLocation     = $IconFile
$Shortcut.Description      = "BroanyX Browser - Privacy-First Tor Browser"
$Shortcut.Save()

Write-Host ""
Write-Host "Desktop shortcut created!" -ForegroundColor Green
Write-Host "  -> $ShortcutPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "Double-click 'BroanyX Browser' on your Desktop to launch." -ForegroundColor White
Write-Host "No terminal or Antigravity needed!" -ForegroundColor White
Write-Host ""
