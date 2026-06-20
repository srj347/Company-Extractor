"""LLM-powered normalization for industry names and location strings.

Batches all unique raw values into a single OpenAI call (structured JSON output)
so ~426 locations + ~95 industries cost ~2 API calls total. Results are cached
to a local JSON file so re-runs don't re-call the API.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from openai import OpenAI

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".normalization_cache"

LOCATION_SYSTEM = """You are a geographic data normalizer. You will receive a JSON array of raw location strings scraped from LinkedIn company profiles.

For each raw string, return a JSON object with:
- "raw": the original string (unchanged)
- "city": the canonical city name in English (e.g., "San Francisco", "Bangalore" not "Bengaluru", "Mumbai" not "Bombay"). Use the most commonly used English name.
- "state": the full state/province/region name (e.g., "California" not "CA", "Karnataka" not "KA", "Maharashtra" not "MH"). null if not applicable or unknown.
- "country": the full country name in English (e.g., "United States of America", "India", "United Kingdom"). Infer from context — "Mountain View, CA" is USA; "Bangalore" is India; "London" is UK.

Rules:
- "Bangalore" and "Bengaluru" are the same city — normalize both to "Bengaluru".
- "Bombay" and "Mumbai" — normalize to "Mumbai".
- US state abbreviations (CA, NY, TX, etc.) must be expanded to full names.
- If the raw string is garbage (e.g., ".", "95877 Bezons", just a number), still try your best — "95877 Bezons" is Bezons, Île-de-France, France.
- If you truly cannot parse it, set all three fields to null.
- Do NOT invent data — if the state is genuinely unknown, set it to null.

Return a JSON array of objects, one per input, in the same order."""

INDUSTRY_SYSTEM = """You are a data normalizer for company industry classifications.

You will receive a JSON array of raw industry strings scraped from LinkedIn.

For each raw string, return a JSON object with:
- "raw": the original string (unchanged)
- "canonical": the canonical industry name

Rules for canonicalization:
- Merge obvious duplicates: "IT Services and IT Consulting" and "Information Technology & Services" → "IT Services and IT Consulting"
- Keep LinkedIn's standard labels when they exist (e.g., "Software Development", "Financial Services", "Business Consulting and Services")
- Don't over-merge: "Computer Hardware Manufacturing" and "Software Development" are different industries
- Normalize casing to Title Case
- If a string is not a real industry, set canonical to null

Return a JSON array of objects, one per input, in the same order."""


class Normalizer:
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4.1-mini"):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model
        CACHE_DIR.mkdir(exist_ok=True)
        self._location_cache = self._load_cache("locations")
        self._industry_cache = self._load_cache("industries")

    # ── public API ───────────────────────────────────────────────────

    def normalize_locations(self, raw_locations: list[str]) -> dict[str, dict]:
        """Return {raw_string: {"city", "state", "country"}} for each input."""
        uncached = [r for r in raw_locations if r not in self._location_cache]
        if uncached:
            print(f"[normalizer] Calling OpenAI to normalize {len(uncached)} locations...",
                  flush=True)
            results = self._batch_call(LOCATION_SYSTEM, uncached, "locations")
            for item in results:
                raw = item.get("raw", "")
                self._location_cache[raw] = {
                    "city": item.get("city"),
                    "state": item.get("state"),
                    "country": item.get("country"),
                }
            self._save_cache("locations", self._location_cache)
        return {r: self._location_cache.get(r, {"city": None, "state": None, "country": None})
                for r in raw_locations}

    def normalize_industries(self, raw_industries: list[str]) -> dict[str, str | None]:
        """Return {raw_string: canonical_name} for each input."""
        uncached = [r for r in raw_industries if r not in self._industry_cache]
        if uncached:
            print(f"[normalizer] Calling OpenAI to normalize {len(uncached)} industries...",
                  flush=True)
            results = self._batch_call(INDUSTRY_SYSTEM, uncached, "industries")
            for item in results:
                raw = item.get("raw", "")
                self._industry_cache[raw] = item.get("canonical")
            self._save_cache("industries", self._industry_cache)
        return {r: self._industry_cache.get(r) for r in raw_industries}

    # ── internals ────────────────────────────────────────────────────

    def _batch_call(self, system: str, items: list[str], label: str) -> list[dict]:
        # Chunk into batches of 100 to stay within token limits.
        all_results = []
        for i in range(0, len(items), 100):
            chunk = items[i : i + 100]
            print(f"  [{label}] batch {i // 100 + 1} ({len(chunk)} items)...",
                  flush=True)
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(chunk, ensure_ascii=False)},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
            text = resp.choices[0].message.content
            parsed = json.loads(text)
            # The model may wrap the array in a key like {"results": [...]}
            if isinstance(parsed, dict):
                for v in parsed.values():
                    if isinstance(v, list):
                        parsed = v
                        break
            if isinstance(parsed, list):
                all_results.extend(parsed)
            else:
                print(f"  [warn] unexpected response shape for {label}, skipping chunk",
                      flush=True)
        return all_results

    def _load_cache(self, name: str) -> dict:
        path = CACHE_DIR / f"{name}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_cache(self, name: str, data: dict) -> None:
        path = CACHE_DIR / f"{name}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
