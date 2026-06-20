"""Configuration for the LinkedIn company-search scraper.

All tunables live here. Secrets / optional proxy come from a `.env` at the
project root (see `.env.example`). Nothing here requires the proxy — leaving it
unset means the scraper uses this machine's normal IP.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent

# Load environment variables from a project-root .env if present (optional).
load_dotenv(PROJECT_ROOT / ".env")

# The faceted company-search URL provided for this POC (HQ-geo filtered).
DEFAULT_SEARCH_URL = (
    "https://www.linkedin.com/search/results/companies/?origin=FACETED_SEARCH&spellCorrectionEnabled=true&companyHqGeo=%5B%22105214831%22%2C%2290009633%22%5D&page=1"
)


def _load_proxy() -> Optional[dict]:
    """Build a Playwright/Camoufox proxy dict from env, or None (dormant)."""
    server = os.getenv("PROXY_SERVER")
    if not server:
        return None
    proxy: dict = {"server": server}
    if os.getenv("PROXY_USERNAME"):
        proxy["username"] = os.getenv("PROXY_USERNAME")
    if os.getenv("PROXY_PASSWORD"):
        proxy["password"] = os.getenv("PROXY_PASSWORD")
    return proxy


@dataclass
class Settings:
    # --- target ---
    search_url: str = DEFAULT_SEARCH_URL
    start_page: int = 1
    # The "injected variable": how many result pages to scrape per run.
    max_pages: int = int(os.getenv("MAX_PAGES", "5"))

    # --- pacing (seconds) — human-like, conservative for a primary account ---
    min_page_delay: float = 4.0
    max_page_delay: float = 9.0
    min_scroll_delay: float = 0.6
    max_scroll_delay: float = 1.8

    # --- browser fingerprint ---
    os_name: str = "macos"          # passed to Camoufox as os=
    humanize: bool = True           # human-like cursor movement
    geoip: bool = True              # derive geo/timezone/locale from egress IP
    locale: str = "en-US"           # force English; geoip still sets timezone/geo

    # --- paths (project root) ---
    profile_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "profile")
    output_path: Path = field(default_factory=lambda: PROJECT_ROOT / "companies.xlsx")
    checkpoint_path: Path = field(default_factory=lambda: PROJECT_ROOT / "checkpoint.json")
    screenshot_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "screenshots")

    # --- network (dormant unless PROXY_SERVER is set in .env) ---
    proxy: Optional[dict] = field(default_factory=_load_proxy)

    def __post_init__(self) -> None:
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    def url_for_page(self, page: int) -> str:
        """Return the search URL with the `page=` query param set to `page`."""
        if re.search(r"[?&]page=\d+", self.search_url):
            return re.sub(r"(page=)\d+", rf"\g<1>{page}", self.search_url)
        sep = "&" if "?" in self.search_url else "?"
        return f"{self.search_url}{sep}page={page}"
