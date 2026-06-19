"""Extract Company Name / Industry / Headquarter Location from result cards.

LinkedIn obfuscates and rotates CSS class names, so we anchor on stable
semantics: each company card contains an `a[href*='/company/']` link. We read
the name from the title link and parse the subtitle line ("Industry • Location")
on the middot. Class-based selectors are tried first, with a text-line fallback.
This JS is the most likely thing to need tweaking when LinkedIn changes markup.
"""

from __future__ import annotations

from datetime import datetime

from .config import Settings
from .models import Company

JS_EXTRACT = r"""
() => {
  const clean = (s) => (s || '').replace(/\s+/g, ' ').trim();

  // Boilerplate lines to drop (cards have action buttons, follower counts,
  // connection insights, and event banners mixed in with the real fields).
  const NOISE_EXACT = /^(Follow|Following|Message|Connect|Connected|Pending|View|See all|Show more|Show less|Promoted|Save|Saved)$/i;
  const FOLLOWERS = /\bfollowers?\b/i;                  // "11M followers"
  const CONNECTIONS = /(works? here|connections? work here|other connection|other connections)/i;
  const HIRED = /(were hired here|alumni were hired)/i;
  const EVENT_TIME = /\b(?:Sun|Mon|Tue|Wed|Thu|Fri|Sat),\s+\w+\s+\d+,/i;  // "Thu, Jun 25, 5:30 PM"
  const BULLET = /^[•·]+$/;

  const looksLikeBoilerplate = (l) =>
    !l || NOISE_EXACT.test(l) || FOLLOWERS.test(l) || CONNECTIONS.test(l) ||
    HIRED.test(l) || EVENT_TIME.test(l) || BULLET.test(l);

  const out = [];
  const seen = new Set();
  const links = Array.from(document.querySelectorAll("a[href*='/company/']"));

  for (const link of links) {
    // Normalize href to /company/<slug> only — strips /events, /posts, /people, etc.
    // so an event sub-link inside a company card doesn't become a phantom row.
    const rawHref = (link.href || '').split('?')[0].split('#')[0];
    const m = rawHref.match(/^(https?:\/\/[^/]+\/company\/[^/]+)/);
    if (!m) continue;
    const href = m[1];
    if (seen.has(href)) continue;

    // Card root: nearest <li>, else a known result container, else parent.
    let card = link.closest('li');
    if (!card) {
      card = link.closest(
        "div.reusable-search__result-container, div.entity-result, " +
        "div.search-result, div[data-chameleon-result-urn], div[data-view-name]"
      );
    }
    if (!card) card = link.parentElement;
    if (!card) continue;

    // The whole card is usually wrapped in one <a>, so positional parsing of
    // innerText lines is more reliable than CSS-class selectors (LinkedIn
    // rotates those frequently).
    const lines = (card.innerText || '')
      .split('\n')
      .map(clean)
      .filter((l) => l && !looksLikeBoilerplate(l));

    if (lines.length === 0) continue;

    // Layout: line 0 = name, line 1 = industry, line 2 = HQ, then overview/etc.
    const name = lines[0];
    if (!name || name.length > 200) continue;

    const industry = (lines[1] && lines[1].length <= 120) ? lines[1] : null;
    const hq = (lines[2] && lines[2].length <= 120) ? lines[2] : null;

    // Overview = longest remaining short-enough line; description paragraphs
    // are typically much longer than industry / HQ / location strings.
    let overview = null;
    let bestLen = 100;
    for (let i = 3; i < lines.length; i++) {
      const l = lines[i];
      if (l.length > bestLen) { overview = l; bestLen = l.length; }
    }
    // Fallback: a line >= 60 chars among 1..2 if line 3+ had nothing.
    if (!overview) {
      for (let i = 1; i < Math.min(lines.length, 3); i++) {
        if (lines[i] && lines[i].length >= 60) { overview = lines[i]; break; }
      }
    }

    // Logo: first <img> in the card with an http(s) src (skip svg/data URIs
    // and ghost placeholders).
    let logo = null;
    const imgs = Array.from(card.querySelectorAll('img'));
    for (const img of imgs) {
      const src = img.currentSrc || img.src ||
                  img.getAttribute('data-delayed-url') || '';
      if (/^https?:\/\//.test(src) && !src.endsWith('.svg') && !src.includes('ghost-')) {
        logo = src;
        break;
      }
    }

    seen.add(href);
    out.push({ name, industry, hq, overview, logo, href });
  }
  return out;
}
"""

# Debug helper: return the raw outerHTML of the first N card roots so selectors
# can be refined against the real (authenticated) DOM.
JS_DUMP = r"""
(n) => {
  const links = Array.from(document.querySelectorAll("a[href*='/company/']"));
  const seen = new Set();
  const cards = [];
  for (const link of links) {
    let card = link.closest('li')
      || link.closest("div.reusable-search__result-container, div.entity-result, div[data-chameleon-result-urn], div[data-view-name]")
      || link.parentElement;
    if (!card) continue;
    const html = card.outerHTML;
    if (seen.has(html)) continue;
    seen.add(html);
    cards.push(html);
    if (cards.length >= n) break;
  }
  return { count: links.length, cards };
}
"""


class CardExtractor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def extract(self, page, source_page: int) -> list[Company]:
        try:
            raw = page.evaluate(JS_EXTRACT)
        except Exception as exc:  # noqa: BLE001
            print(f"[extract] page.evaluate failed: {exc!r}", flush=True)
            return []

        ts = datetime.now().isoformat(timespec="seconds")
        companies: list[Company] = []
        for r in raw or []:
            name = (r.get("name") or "").strip()
            if not name:
                continue
            companies.append(
                Company(
                    name=name,
                    industry=(r.get("industry") or None),
                    hq_location=(r.get("hq") or None),
                    overview=(r.get("overview") or None),
                    logo_url=(r.get("logo") or None),
                    profile_url=(r.get("href") or None),
                    source_page=source_page,
                    scraped_at=ts,
                )
            )
        return companies

    def dump_sample(self, page, path, n: int = 3) -> int:
        """Write the outerHTML of the first `n` card roots to `path` (debug)."""
        from pathlib import Path as _Path

        try:
            data = page.evaluate(JS_DUMP, n)
        except Exception as exc:  # noqa: BLE001
            print(f"[debug] dump failed: {exc!r}", flush=True)
            return 0
        cards = data.get("cards", []) if isinstance(data, dict) else []
        body = "\n\n<!-- ===== NEXT CARD ===== -->\n\n".join(cards)
        header = f"<!-- company links found on page: {data.get('count')} -->\n"
        _Path(path).write_text(header + body, encoding="utf-8")
        return len(cards)
