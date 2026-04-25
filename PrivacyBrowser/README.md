# 🛡️ PrivacyBrowser — Hybrid Architecture

**A fully functional, highly secure desktop browser built on a high-performance hybrid stack:**
- **Frontend:** Python 3.10+ · PyQt6 · PyQt6-WebEngine
- **Backend:** Go (Golang) proxy engine
- **Anonymity:** Tor daemon

---

## 🏗️ Architecture Overview

```
  ┌─────────────────────────────────────────────────────────────┐
  │                     USER'S COMPUTER                         │
  │                                                             │
  │  ┌──────────────────────────┐                               │
  │  │   PyQt6 Browser (Python) │                               │
  │  │   - Dark-mode UI         │                               │
  │  │   - Tab management       │  HTTP Proxy                   │
  │  │   - Privacy hardening    │ ──────────────►               │
  │  │   - Tor/Proxy indicators │   127.0.0.1:8080              │
  │  └──────────────────────────┘         │                     │
  │                                       ▼                     │
  │                        ┌─────────────────────────────┐      │
  │                        │  Go Proxy Engine             │      │
  │                        │  - EasyList ad-blocking      │      │
  │                        │  - Domain blocklist (O(1))   │      │
  │                        │  - CONNECT tunnel handler    │ SOCKS5│
  │                        │  - HTTP relay handler        │ ─────►│
  │                        │  /__proxy_status endpoint    │  :9050│
  │                        └─────────────────────────────┘      │
  │                                       │                     │
  │                                       ▼                     │
  │                        ┌─────────────────────────────┐      │
  │                        │  Tor Daemon (stem-managed)   │      │
  │                        │  - SOCKS5 on 127.0.0.1:9050  │      │
  │                        │  - .onion support            │      │
  │                        │  - 3-hop circuit encryption  │      │
  │                        └─────────────────────────────┘      │
  │                                       │                     │
  └───────────────────────────────────────┼─────────────────────┘
                                          ▼
                              🌐 Internet / Dark Web
```

**Data flow:**  
`Browser → Go Proxy (:8080) → [AdBlock check] → Tor SOCKS5 (:9050) → Internet`

Ads are dropped **before** they ever reach Tor — saving bandwidth and improving speed.

---

## 📁 Project Structure

```
PrivacyBrowser/
├── backend/                    ← Go proxy engine
│   ├── main.go                 ← Full proxy server source
│   ├── go.mod                  ← Go module (proxy_engine)
│   ├── go.sum
│   └── proxy_engine.exe        ← Compiled binary (built by you)
│
└── frontend/                   ← Python PyQt6 browser
    ├── main.py                 ← Entry point (run this!)
    ├── browser_window.py       ← Main window — UI, toolbar, menus
    ├── tor_manager.py          ← Tor daemon lifecycle (stem)
    ├── proxy_manager.py        ← Go proxy subprocess manager
    ├── privacy_settings.py     ← WebEngine privacy hardening
    ├── tab_widget.py           ← Custom tabbed browsing
    ├── web_view.py             ← Custom QWebEngineView
    ├── assets/
    │   └── style.qss           ← Dark-mode Qt stylesheet
    ├── requirements.txt
    └── setup.ps1               ← One-click venv + install
```

---

## 🔧 Prerequisites

### 1. Python 3.10+
Download from [python.org](https://python.org/downloads/). ✅ Add to PATH during install.

### 2. Go 1.21+
Download from [go.dev](https://go.dev/dl/). ✅ Installer adds to PATH automatically.

### 3. Tor Expert Bundle
Download from [torproject.org/download/tor/](https://www.torproject.org/download/tor/).

```powershell
# Windows options:
# Option A: Extract Expert Bundle, add Tor\ folder to PATH
# Option B: Install full Tor Browser — bundled tor.exe auto-detected

# The browser searches these automatically:
#   C:\Program Files\Tor Browser\Browser\TorBrowser\Tor\tor.exe
#   C:\tor\tor.exe
#   D:\tor\tor.exe  (and many more)
#   System PATH
```

---

## 🚀 Quick Start

### Step 1 — Build the Go proxy

```powershell
cd d:\broswer\PrivacyBrowser\backend
go mod tidy
go build -o proxy_engine.exe .
# → proxy_engine.exe created ✅
```

### Step 2 — Set up the Python frontend

```powershell
cd d:\broswer\PrivacyBrowser\frontend

# One-click setup (creates venv + installs packages):
.\setup.ps1

# Or manually:
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Step 3 — Launch!

```powershell
cd d:\broswer\PrivacyBrowser\frontend
.\venv\Scripts\python.exe main.py
```

The browser will:
1. Start the Go proxy engine on `:8080` 
2. Launch Tor on `:9050` (bootstrap takes 15-60s)  
3. Open to DuckDuckGo when both are ready

---

## ✨ Features

| Feature | Details |
|---------|---------|
| ⚙️ **Go Proxy Engine** | Local HTTP proxy on `:8080`. Blocks ads server-side, tunnels via Tor |
| 🚫 **EasyList Ad-Blocking** | 80,000+ domains blocked. Refreshes every 24h. Counts shown live |
| 🧅 **Tor Integration** | All traffic through `:9050`. Full `.onion` v3 support |
| 🔒 **Privacy Hardening** | No persistent cookies · WebRTC minimised · Geolocation denied |
| 🌑 **Dark Mode UI** | Deep navy/purple theme · Glassmorphism tabs · Animated status pills |
| 🗂️ **Tabbed Browsing** | Drag tabs · Middle-click close · New-tab button · Favicons |
| 🔍 **Smart URL Bar** | Auto-detects URLs vs searches (DuckDuckGo). HTTPS padlock |
| 📊 **Status Indicators** | Go proxy pill + Tor pill + live blocked-ad counter |
| ⌨️ **Shortcuts** | `Ctrl+T` new tab · `Ctrl+W` close · `Ctrl+L` URL bar · `F5` reload |

---

## 🔒 Privacy Details

### Traffic Chain
```
PyQt6 Browser
    ↓ HTTP proxy (all requests including HTTPS CONNECT)
Go Proxy :8080
    ↓ if domain NOT blocked:
Tor SOCKS5 :9050
    ↓ encrypted 3-hop circuit
Internet
```

### Go Backend — Ad Blocking
- Downloads EasyList + EasyPrivacy on startup (~80,000 domains)
- Parses `||domain.com^` rules into a Go `map[string]struct{}` for O(1) lookup
- Blocked requests get `403 Forbidden` — **never** reach Tor
- `/__proxy_status` JSON endpoint: `{"status":"running","blocked_count":123,...}`

### Go Backend — Tor Routing
- Uses `golang.org/x/net/proxy` SOCKS5 dialer pointed at `127.0.0.1:9050`
- `CONNECT` tunnels: hijacks connection, dials target through Tor, bidirectional pipe
- Plain `HTTP`: creates per-request transport with Tor dialer, relays response

### Python Frontend — Privacy Hardening

| Setting | Value |
|---------|-------|
| Proxy | HTTP via Go proxy `:8080` (not direct SOCKS5) |
| Persistent cookies | ❌ Disabled |
| WebRTC | `WebRTCPublicInterfacesOnly = True` |
| Geolocation | ❌ Always denied |
| Notifications | ❌ Always denied |
| Microphone / Camera | ❌ Always denied |
| User-Agent | `Mozilla/5.0 (Windows NT 10.0; rv:121.0) Firefox/121.0` |
| Accept-Language | `en-US,en;q=0.9` |
| Spell-check | ❌ Disabled |
| HTTP cache | Session-only (no persistence) |

---

## ⚙️ Menus

### Privacy Menu
- **Clear Cookies & Cache** — wipes session data
- **Check Tor** — opens `check.torproject.org`
- **Check My IP** — opens `whatismyip.com`

### View Menu
- **JavaScript Enabled** — toggle JS
- **Zoom In/Out/Reset** — `Ctrl++` / `Ctrl+-` / `Ctrl+0`

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|---------|
| `⚙️ Proxy Offline` | `proxy_engine.exe` not built or failed. Rebuild: `go build -o proxy_engine.exe .` |
| `⚠️ Tor Offline` | Install Tor Expert Bundle and add to PATH |
| Tor takes >60s | Normal on first run. Subsequent starts are faster (cached consensus) |
| Ad rules slow to load | Go proxy downloads EasyList on first start. Wait ~10s |
| Pages not loading | Ensure both proxy and Tor pills are **green** |
| `.onion` not resolving | Confirm Tor is green. `.onion` DNS resolves through Tor automatically |
| `ModuleNotFoundError` | Activate venv: `.\venv\Scripts\Activate.ps1` |
| Go not found | Add Go to PATH: `$env:PATH = "C:\Program Files\Go\bin;" + $env:PATH` |

---

## 📜 License

MIT License — free to use, modify, and distribute.

---

> ⚠️ **Legal Notice:** This browser is for privacy research and legitimate anonymity use.
> Tor is legal in most countries. Do not use for illegal activities. Developers are not
> responsible for misuse. Check your local laws.
