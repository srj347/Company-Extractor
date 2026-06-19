"""Orchestrator: login (human-in-loop) -> paginate -> extract -> Excel.

Usage:
    python -m linkedin_company_scraper.main --pages 1
    python -m linkedin_company_scraper.main --pages 5
    python -m linkedin_company_scraper.main --fresh --pages 3
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

from .auth import AuthManager
from .browser import BrowserManager
from .config import Settings
from .detection import CheckpointDetected, DetectionGuard
from .extractor import CardExtractor
from .navigator import SearchNavigator
from .storage import CheckpointStore, ExcelWriter


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="LinkedIn company-search scraper (Camoufox anti-detect Firefox)."
    )
    p.add_argument("--pages", type=int, default=None,
                   help="Number of result pages to scrape (overrides MAX_PAGES).")
    p.add_argument("--start-page", type=int, default=None,
                   help="Page to start from (default: resume from checkpoint, else 1).")
    p.add_argument("--url", type=str, default=None, help="Override the search URL.")
    p.add_argument("--out", type=str, default=None, help="Output .xlsx path.")
    p.add_argument("--fresh", action="store_true",
                   help="Ignore the checkpoint and start fresh.")
    p.add_argument("--debug-dump", action="store_true",
                   help="Save the raw HTML of the first few cards to debug_card.html "
                        "(use to refine extractor selectors against the live DOM).")
    return p.parse_args(argv)


def _resolve_start_page(args, settings, checkpoint) -> int:
    if args.start_page is not None:
        return args.start_page
    if args.fresh:
        return settings.start_page
    return max(settings.start_page, checkpoint.last_completed_page() + 1)


def main(argv=None) -> int:
    args = parse_args(argv)

    settings = Settings()
    if args.pages is not None:
        settings.max_pages = args.pages
    if args.url:
        settings.search_url = args.url
    if args.out:
        settings.output_path = Path(args.out)

    writer = ExcelWriter(settings.output_path)
    checkpoint = CheckpointStore(settings.checkpoint_path)
    start_page = _resolve_start_page(args, settings, checkpoint)

    browser = BrowserManager(settings)
    auth = AuthManager(settings)
    nav = SearchNavigator(settings)
    extractor = CardExtractor(settings)
    guard = DetectionGuard(settings)

    total_added = 0
    try:
        page = browser.launch()

        if not auth.is_logged_in(page):
            auth.human_login(page)

        first_url = settings.url_for_page(start_page)
        print(f"[scrape] Navigating to page {start_page}: {first_url}", flush=True)
        nav.goto_search(page, first_url)
        guard.assert_not_blocked(page)

        current = start_page
        pages_done = 0
        while pages_done < settings.max_pages:
            print(f"[scrape] Page {current}: loading cards...", flush=True)
            nav.scroll_to_load(page)

            if args.debug_dump and pages_done == 0:
                dump_path = Path(settings.output_path).parent / "debug_card.html"
                n = extractor.dump_sample(page, dump_path)
                print(f"[debug] Wrote {n} sample card(s) to {dump_path}", flush=True)

            companies = extractor.extract(page, current)
            for c in companies[:3]:
                ov = (c.overview or "")[:60] + ("..." if c.overview and len(c.overview) > 60 else "")
                print(
                    f"        • {c.name!r} | industry={c.industry!r} | "
                    f"hq={c.hq_location!r} | logo={'Y' if c.logo_url else 'N'} | overview={ov!r}",
                    flush=True,
                )
            added = writer.append(companies)
            total_added += added
            checkpoint.save(current)
            print(
                f"[scrape] Page {current}: extracted {len(companies)}, "
                f"new rows {added} (file total {writer.total_rows}).",
                flush=True,
            )

            pages_done += 1
            if pages_done >= settings.max_pages:
                break

            delay = random.uniform(settings.min_page_delay, settings.max_page_delay)
            print(f"[scrape] Waiting {delay:.1f}s before next page...", flush=True)
            time.sleep(delay)

            if not nav.next_page(page, current):
                print("[scrape] No further pages (end of results).", flush=True)
                break
            current += 1
            guard.assert_not_blocked(page)

        print(
            f"\n[done] Added {total_added} new companies. "
            f"Workbook: {settings.output_path} ({writer.total_rows} rows total).",
            flush=True,
        )
        return 0

    except CheckpointDetected as exc:
        print(f"\n[STOP] {exc}", flush=True)
        print(f"[STOP] Data saved so far: {settings.output_path} "
              f"({writer.total_rows} rows).", flush=True)
        return 2
    except KeyboardInterrupt:
        print("\n[interrupted] Saving and exiting.", flush=True)
        return 130
    finally:
        browser.close()


if __name__ == "__main__":
    sys.exit(main())
