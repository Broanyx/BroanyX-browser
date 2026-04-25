<div align="center">
  <img src="assets/icon.png" width="120" height="120" style="border-radius:24px" />
  <h1>BroanyX Browser</h1>
  <p><strong>Privacy-First · Tor-Routed · Ad-Free Desktop Browser</strong></p>

  [![Release](https://img.shields.io/github/v/release/Broanyx/BroanyX-browser?style=flat-square&color=7c3aed)](https://github.com/Broanyx/BroanyX-browser/releases/latest)
  [![License](https://img.shields.io/github/license/Broanyx/BroanyX-browser?style=flat-square&color=22c55e)](LICENSE)
  [![Platform](https://img.shields.io/badge/platform-Windows-blue?style=flat-square)](https://github.com/Broanyx/BroanyX-browser/releases)
  [![Built with PyQt6](https://img.shields.io/badge/built%20with-PyQt6-a855f7?style=flat-square)](https://pypi.org/project/PyQt6/)

</div>

---

## Features

| Feature | Details |
|---|---|
| 🧅 **Tor Routing** | All traffic goes through the Tor anonymity network |
| 🚫 **Ad Blocking** | EasyList + EasyPrivacy — blocked at network level |
| 🔒 **WebRTC Disabled** | No IP leaks via WebRTC |
| 🕵️ **User-Agent Spoofed** | Randomized fingerprint every session |
| 🌐 **Dark Web Support** | Browse `.onion` sites natively |
| 🔄 **Auto-Updates** | In-app notification when new versions are released |
| ⚡ **Fast & Lightweight** | Built on Chromium via PyQt6 WebEngine |

---

## Download

👉 **[Download BroanyX-Setup.exe](https://github.com/Broanyx/BroanyX-browser/releases/latest)**

- Windows 10 / 11 (64-bit)
- No Python required — fully standalone
- ~140 MB installer

---

## Screenshots

> *Privacy-first browsing with Tor status, ad-block counter, and dark UI*

---

## Build From Source

### Requirements
- Python 3.10+ 
- Windows 10/11

### Setup

```powershell
# Clone the repo
git clone https://github.com/Broanyx/BroanyX-browser.git
cd BroanyX-browser

# Create virtual environment & install dependencies
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt

# Run the browser
.\venv\Scripts\python.exe main.py
```

### Build Installer

```powershell
# Requires Inno Setup: https://jrsoftware.org/isdl.php
.\build.ps1
# Output: dist\BroanyX-Setup.exe
```

---

## Auto-Update System

BroanyX checks `version.json` on this repo on every launch.  
When you release a new version:

1. Bump `APP_VERSION` in `main.py` and `updater.py`
2. Run `.\build.ps1`
3. Upload `BroanyX-Setup.exe` to [GitHub Releases](https://github.com/Broanyx/BroanyX-browser/releases)
4. Update `version.json` with the new version number

→ All installed copies will show an in-app update banner on next launch!

---

## Project Structure

```
BroanyX-browser/
├── main.py              # Entry point — app bootstrap
├── browser_window.py    # Main window UI
├── tab_widget.py        # Tab management
├── web_view.py          # WebView with privacy hooks
├── adblocker.py         # Ad-block interceptor
├── privacy_settings.py  # Privacy hardening
├── tor_manager.py       # Tor daemon manager
├── updater.py           # Auto-update checker
├── version.json         # Current version manifest
├── assets/
│   ├── icon.ico         # App icon (Windows)
│   ├── icon.png         # App icon (PNG)
│   └── style.qss        # Dark theme stylesheet
├── installer/
│   └── BroanyX-InnoSetup.iss  # Inno Setup installer script
├── website/
│   └── index.html       # Download website
├── build.ps1            # One-click build script
└── requirements.txt     # Python dependencies
```

---

## License

MIT License — free to use, modify, and distribute.

---

<div align="center">
  <sub>Built with Python, PyQt6, and open-source privacy tools.</sub>
</div>
