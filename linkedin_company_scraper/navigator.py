"""Navigation: load the search page, lazy-load all cards, paginate."""

from __future__ import annotations

import random
import time

from .config import Settings

# Every company result on the page links to /company/<id>/
COMPANY_LINK = "a[href*='/company/']"


class SearchNavigator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def goto_search(self, page, url: str) -> None:
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        try:
            page.wait_for_selector(COMPANY_LINK, timeout=20_000)
        except Exception:
            # Could be an empty result set; the caller handles a zero count.
            pass

    def scroll_to_load(self, page) -> int:
        """Scroll until the company-link count stops growing (lazy hydration)."""
        s = self.settings
        last_count = -1
        stable = 0
        for _ in range(25):
            count = page.locator(COMPANY_LINK).count()
            if count == last_count:
                stable += 1
                if stable >= 2:
                    break
            else:
                stable = 0
            last_count = count
            self._scroll_down(page, random.randint(600, 1100))
            time.sleep(random.uniform(s.min_scroll_delay, s.max_scroll_delay))

        # Settle back near the top.
        try:
            page.evaluate("window.scrollTo(0, 0)")
        except Exception:
            pass
        time.sleep(random.uniform(0.4, 1.0))
        return max(last_count, 0)

    def next_page(self, page, current: int) -> bool:
        """Advance to page `current + 1`. Returns False at the end of results."""
        # Strategy 1: click the 'Next' pagination button (most human-like).
        try:
            nxt = page.locator("button[aria-label='Next']").first
            if nxt.count() > 0 and nxt.is_enabled():
                nxt.scroll_into_view_if_needed(timeout=5_000)
                nxt.click(timeout=5_000)
                page.wait_for_load_state("domcontentloaded")
                try:
                    page.wait_for_selector(COMPANY_LINK, timeout=15_000)
                except Exception:
                    pass
                return True
        except Exception:
            pass

        # Strategy 2: bump the page= URL param.
        try:
            page.goto(self.settings.url_for_page(current + 1),
                      wait_until="domcontentloaded", timeout=60_000)
            try:
                page.wait_for_selector(COMPANY_LINK, timeout=12_000)
            except Exception:
                pass
            return page.locator(COMPANY_LINK).count() > 0
        except Exception:
            return False

    def _scroll_down(self, page, delta: int) -> None:
        try:
            page.mouse.wheel(0, delta)
        except Exception:
            try:
                page.evaluate(f"window.scrollBy(0, {delta})")
            except Exception:
                pass
