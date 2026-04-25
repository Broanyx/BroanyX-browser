"""
privacy_settings.py
-------------------
Applies privacy hardening to QWebEngineProfile.

Routes ALL traffic through the Go proxy (127.0.0.1:8080).
The Go proxy handles Tor routing internally.
"""

import logging

logger = logging.getLogger(__name__)

SPOOFED_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
    "Gecko/20100101 Firefox/121.0"
)


def apply_privacy_settings(
    profile,
    proxy_host: str = "127.0.0.1",
    proxy_port: int = 8080,
):
    """
    Apply privacy settings and route traffic through the Go proxy.

    Args:
        profile:    QWebEngineProfile instance
        proxy_host: Go proxy host (default 127.0.0.1)
        proxy_port: Go proxy port (default 8080)
    """
    from PyQt6.QtNetwork import QNetworkProxy
    from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings

    # ── 1. Route ALL traffic through the Go proxy (HTTP proxy) ─────────────
    proxy = QNetworkProxy()
    proxy.setType(QNetworkProxy.ProxyType.HttpProxy)
    proxy.setHostName(proxy_host)
    proxy.setPort(proxy_port)
    QNetworkProxy.setApplicationProxy(proxy)
    logger.info(f"Proxy set: HTTP {proxy_host}:{proxy_port} (Go proxy → Tor)")

    # ── 2. Spoof User-Agent ─────────────────────────────────────────────────
    profile.setHttpUserAgent(SPOOFED_USER_AGENT)
    logger.info(f"User-Agent spoofed: {SPOOFED_USER_AGENT}")

    # ── 3. Cookie policy — no persistent cookies ────────────────────────────
    profile.setPersistentCookiesPolicy(
        QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
    )
    logger.info("Cookie policy: NoPersistentCookies")

    # ── 4. WebEngine settings ───────────────────────────────────────────────
    settings = profile.settings()

    # Minimize WebRTC IP leakage (public interfaces only — belt-and-suspenders)
    settings.setAttribute(
        QWebEngineSettings.WebAttribute.WebRTCPublicInterfacesOnly, True
    )

    # Keep JS enabled (required for most sites)
    settings.setAttribute(
        QWebEngineSettings.WebAttribute.JavascriptEnabled, True
    )

    # Disable spell-check (avoids sending typed text to remote APIs)
    profile.setSpellCheckEnabled(False)

    logger.info("WebEngine privacy settings applied.")

    # ── 5. Accept-Language — generic value ─────────────────────────────────
    profile.setHttpAcceptLanguage("en-US,en;q=0.9")

    logger.info(f"Profile is off-the-record: {profile.isOffTheRecord()}")


def deny_geo_permission(page, security_origin, feature):
    """Always deny geolocation and other sensitive permissions."""
    from PyQt6.QtWebEngineCore import QWebEnginePage
    page.setFeaturePermission(
        security_origin,
        feature,
        QWebEnginePage.PermissionPolicy.PermissionDeniedByUser,
    )
    logger.debug(f"Denied permission {feature} for: {security_origin.toString()}")
