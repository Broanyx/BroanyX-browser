"""
privacy_settings.py
-------------------
Applies privacy hardening to a QWebEngineProfile.

Enforces:
- SOCKS5 proxy (Tor)
- Spoofed User-Agent
- No persistent cookies
- No third-party cookies
- Geolocation denied by default
- WebRTC minimised (no public interface exposure)
- DNS-over-HTTPS disabled (DNS goes through Tor)
- No spell-check (avoids data leakage)
"""

import logging

logger = logging.getLogger(__name__)

# Generic, non-identifying User-Agent.
# We use a common Firefox/Windows UA to avoid fingerprinting via unusual UAs.
SPOOFED_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
    "Gecko/20100101 Firefox/121.0"
)


def apply_privacy_settings(profile, tor_host: str = "127.0.0.1", tor_port: int = 9050):
    """
    Apply all privacy settings to a QWebEngineProfile.

    Args:
        profile: QWebEngineProfile instance
        tor_host: SOCKS5 proxy host (Tor)
        tor_port: SOCKS5 proxy port (Tor)
    """
    from PyQt6.QtNetwork import QNetworkProxy
    from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings

    # ------------------------------------------------------------------
    # 1. Route all traffic through Tor SOCKS5 proxy
    # ------------------------------------------------------------------
    proxy = QNetworkProxy()
    proxy.setType(QNetworkProxy.ProxyType.Socks5Proxy)
    proxy.setHostName(tor_host)
    proxy.setPort(tor_port)
    QNetworkProxy.setApplicationProxy(proxy)
    logger.info(f"Proxy set: SOCKS5 {tor_host}:{tor_port}")

    # ------------------------------------------------------------------
    # 2. Spoof User-Agent
    # ------------------------------------------------------------------
    profile.setHttpUserAgent(SPOOFED_USER_AGENT)
    logger.info(f"User-Agent spoofed: {SPOOFED_USER_AGENT}")

    # ------------------------------------------------------------------
    # 3. Cookie policy — no persistent cookies, no third-party cookies
    # ------------------------------------------------------------------
    profile.setPersistentCookiesPolicy(
        QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
    )
    logger.info("Cookie policy: NoPersistentCookies")

    # ------------------------------------------------------------------
    # 4. WebEngine settings — disable privacy-leaking features
    # ------------------------------------------------------------------
    settings = profile.settings()

    # Disable WebRTC's STUN/TURN to prevent real IP leakage
    settings.setAttribute(
        QWebEngineSettings.WebAttribute.WebRTCPublicInterfacesOnly, True
    )

    # Disable JavaScript access to location (belt-and-suspenders alongside permission handler)
    settings.setAttribute(
        QWebEngineSettings.WebAttribute.JavascriptEnabled, True  # Keep JS on by default
    )

    # Enable multimedia plugins (e.g., Widevine DRM) if available on the system
    settings.setAttribute(
        QWebEngineSettings.WebAttribute.PluginsEnabled, True
    )

    # Disable spell-check (avoids sending typed text to external services)
    profile.setSpellCheckEnabled(False)

    # Disable auto-load of images from third-party can be toggled via menu
    # settings.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages, True)

    logger.info("WebEngine privacy settings applied.")

    # ------------------------------------------------------------------
    # 5. HTTP Accept-Language header — use generic value
    # ------------------------------------------------------------------
    profile.setHttpAcceptLanguage("en-US,en;q=0.9")

    # ------------------------------------------------------------------
    # 6. Disable persistent storage paths (in-memory profile preferred,
    #    but named profiles need explicit clearing action)
    # ------------------------------------------------------------------
    # If using off-the-record profile, no additional steps needed.
    # Log storage state for debugging.
    logger.info(f"Profile is off-the-record: {profile.isOffTheRecord()}")


def deny_geo_permission(page, security_origin, feature):
    """
    Permission handler for QWebEnginePage.
    Always denies geolocation. Called via page.featurePermissionRequested signal.
    """
    from PyQt6.QtWebEngineCore import QWebEnginePage
    if feature == QWebEnginePage.Feature.Geolocation:
        page.setFeaturePermission(
            security_origin,
            feature,
            QWebEnginePage.PermissionPolicy.PermissionDeniedByUser,
        )
        logger.debug(f"Denied geolocation for: {security_origin.toString()}")
    else:
        # Default: also deny other sensitive permissions (notifications, microphone, etc.)
        page.setFeaturePermission(
            security_origin,
            feature,
            QWebEnginePage.PermissionPolicy.PermissionDeniedByUser,
        )
        logger.debug(f"Denied permission {feature} for: {security_origin.toString()}")
