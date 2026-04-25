"""
adblocker.py
------------
Engine-level ad/tracker blocker.

Downloads EasyList + EasyPrivacy on first run (cached locally).
Subclasses QWebEngineUrlRequestInterceptor to block matching requests
before they ever hit the network.
"""

import os
import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# EasyList + EasyPrivacy combined for better tracker coverage
AD_LIST_URLS = [
    "https://easylist.to/easylist/easylist.txt",
    "https://easylist.to/easylist/easyprivacy.txt",
]

# Local cache directory (next to this file)
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".adblock_cache")
CACHED_RULES_FILE = os.path.join(CACHE_DIR, "combined_rules.txt")


def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def download_rules(force_refresh: bool = False) -> list[str]:
    """
    Download EasyList rules. Returns list of rule strings.
    Uses cached copy if present and force_refresh is False.
    """
    _ensure_cache_dir()

    if os.path.isfile(CACHED_RULES_FILE) and not force_refresh:
        logger.info(f"Loading ad rules from cache: {CACHED_RULES_FILE}")
        with open(CACHED_RULES_FILE, "r", encoding="utf-8") as f:
            return f.read().splitlines()

    logger.info("Downloading EasyList + EasyPrivacy...")
    combined = []

    try:
        import requests
        for url in AD_LIST_URLS:
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                lines = resp.text.splitlines()
                combined.extend(lines)
                logger.info(f"Downloaded {len(lines)} rules from {url}")
            except Exception as e:
                logger.warning(f"Failed to download {url}: {e}")

        # Cache to disk
        with open(CACHED_RULES_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(combined))

        logger.info(f"Cached {len(combined)} combined ad-block rules.")
    except ImportError:
        logger.error("requests library not available — cannot download EasyList.")

    return combined


class AdBlockInterceptor:
    """
    Wraps adblockparser.AdblockRules and provides a simple .should_block(url) API.
    Loads rules asynchronously so it doesn't slow down startup.
    """

    def __init__(self):
        self._blocked_domains = set()
        self._ready = False
        self._blocked_count = 0
        self._load_thread = threading.Thread(target=self._load_rules, daemon=True)
        self._load_thread.start()

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def blocked_count(self) -> int:
        return self._blocked_count

    def should_block(self, url: str) -> bool:
        """
        Returns True if the requested URL's domain (or parent domain) is 
        in the adblock domain list. Runs in O(1) time.
        """
        if not self._ready:
            return False
        
        try:
            from urllib.parse import urlparse
            host = urlparse(url).hostname
            if not host:
                return False
                
            host = host.lower()
            # Check exact host and parent domains (e.g. sub.ad.com -> ad.com)
            parts = host.split('.')
            for i in range(len(parts) - 1):
                parent_domain = ".".join(parts[i:])
                if parent_domain in self._blocked_domains:
                    return True
            return False
        except Exception:
            return False

    def _load_rules(self):
        """Extract domain names from EasyList and store in an O(1) lookup set."""
        try:
            rules_lines = download_rules()
            domains = set()
            
            # Very basic extraction of domains from EasyList syntax
            # E.g., "||doubleclick.net^" -> "doubleclick.net"
            for line in rules_lines:
                line = line.strip()
                if line.startswith("||") and line.endswith("^"):
                    domain = line[2:-1]
                    # Exclude rules that have paths or wildcards
                    if "/" not in domain and "*" not in domain:
                        domains.add(domain.lower())

            self._blocked_domains = domains
            self._ready = True
            logger.info(f"Fast Ad-block ready: Loaded {len(domains)} tracker domains.")
        except Exception as e:
            logger.error(f"Failed to load ad-block rules: {e}")


# ---------------------------------------------------------------------------
# Qt request interceptor (PyQt6)
# ---------------------------------------------------------------------------

try:
    from PyQt6.QtWebEngineCore import QWebEngineUrlRequestInterceptor, QWebEngineUrlRequestInfo

    class RequestInterceptor(QWebEngineUrlRequestInterceptor):
        """
        Plugged into QWebEngineProfile.setUrlRequestInterceptor().
        Intercepts every outbound request and blocks ad/tracker URLs.
        """

        def __init__(self, ad_blocker: AdBlockInterceptor, parent=None):
            super().__init__(parent)
            self._ad_blocker = ad_blocker

        def interceptRequest(self, info: QWebEngineUrlRequestInfo):  # noqa: N802
            url = info.requestUrl().toString()

            if self._ad_blocker.should_block(url):
                self._ad_blocker._blocked_count += 1
                logger.debug(f"BLOCKED: {url}")
                info.block(True)

except ImportError:
    # If PyQt6 not installed yet, provide stub so module still imports cleanly
    class RequestInterceptor:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass
