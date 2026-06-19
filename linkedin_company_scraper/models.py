"""Data model for an extracted company row."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Company:
    name: str
    industry: Optional[str]
    hq_location: Optional[str]
    overview: Optional[str]
    logo_url: Optional[str]
    profile_url: Optional[str]
    source_page: int
    scraped_at: str

    def as_row(self) -> list:
        """Order must match storage.HEADERS."""
        return [
            self.name,
            self.industry,
            self.hq_location,
            self.overview,
            self.logo_url,
            self.profile_url,
            self.source_page,
            self.scraped_at,
        ]
