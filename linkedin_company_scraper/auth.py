"""Authentication with a human in the loop.

We never automate Google credentials / 2FA. Instead we open the login page,
best-effort click the Google button, then wait (event-based) for the LinkedIn
feed to load, which means the human finished. The session is persisted by the
browser profile, so this only happens once.
"""

from __future__ import annotations

FEED_URL = "https://www.linkedin.com/feed/"
LOGIN_URL = "https://www.linkedin.com/login"

# Selectors that only exist when authenticated (LinkedIn global nav).
LOGGED_IN_MARKERS = (
    "img.global-nav__me-photo",
    "div.global-nav__me",
    "button[aria-label*='settings and privacy' i]",
    "[data-control-name='nav.settings']",
)


class AuthManager:
    def __init__(self, settings) -> None:
        self.settings = settings

    def is_logged_in(self, page) -> bool:
        try:
            page.goto(FEED_URL, wait_until="domcontentloaded", timeout=30_000)
        except Exception:
            return False

        url = (page.url or "").lower()
        if any(x in url for x in ("/login", "authwall", "/checkpoint", "/signup")):
            return False

        for sel in LOGGED_IN_MARKERS:
            try:
                if page.locator(sel).first.count() > 0:
                    return True
            except Exception:
                continue

        # Fallback: the li_at auth cookie.
        try:
            cookies = page.context.cookies("https://www.linkedin.com")
            return any(c.get("name") == "li_at" for c in cookies)
        except Exception:
            return False

    def human_login(self, page) -> None:
        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60_000)
        except Exception:
            pass

        print("\n" + "=" * 72)
        print("  HUMAN ACTION REQUIRED")
        print("  1. In the browser window, click 'Sign in with Google'")
        print("  2. Complete Google login (including any 2FA / verification)")
        print("  3. Wait until your LinkedIn feed is fully visible")
        print("  4. Return here and press Enter to continue the script")
        print("=" * 72 + "\n", flush=True)

        # Block on Enter — avoids holding an active Playwright event listener
        # during the Google OAuth popup, which triggers a known Playwright/Firefox
        # crash when the popup emits a JS error without a location object.
        try:
            input("  Press Enter after your LinkedIn feed has loaded... ")
        except EOFError:
            pass

        # Navigate to feed ourselves to confirm the session.
        if not self.is_logged_in(page):
            raise RuntimeError(
                "Login not detected — refusing to scrape while logged out. "
                "Re-run and complete the Google sign-in before pressing Enter."
            )
        print("[auth] Logged in. Session saved to the persistent profile.", flush=True)
