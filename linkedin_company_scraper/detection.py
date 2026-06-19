"""Detect LinkedIn security checkpoints / CAPTCHAs and stop the run.

Primary-account safety rule: never push through a checkpoint. On detection we
screenshot and raise CheckpointDetected so the orchestrator stops cleanly with
data already flushed.
"""

from __future__ import annotations

# Strong signals in the URL (reliable).
URL_MARKERS = ("checkpoint", "captcha", "authwall", "/uas/", "security-verification")
# Strong signals in title/body text (kept specific to avoid false positives).
TEXT_MARKERS = (
    "let's do a quick security check",
    "verify you're a human",
    "we've restricted",
    "unusual activity",
    "are you a human",
    "complete this security check",
)


class CheckpointDetected(Exception):
    """Raised when LinkedIn shows a checkpoint/CAPTCHA/auth wall."""


class DetectionGuard:
    def __init__(self, settings) -> None:
        self.settings = settings

    def assert_not_blocked(self, page) -> None:
        url = (page.url or "").lower()
        for m in URL_MARKERS:
            if m in url:
                self._raise(page, f"url contains '{m}'")

        title = ""
        body = ""
        try:
            title = (page.title() or "").lower()
        except Exception:
            pass
        try:
            body = page.locator("body").inner_text(timeout=3_000).lower()[:4000]
        except Exception:
            pass

        haystack = f"{title}\n{body}"
        for m in TEXT_MARKERS:
            if m in haystack:
                self._raise(page, f"text contains '{m}'")

    def _raise(self, page, reason: str) -> None:
        shot = self.settings.screenshot_dir / "checkpoint.png"
        try:
            page.screenshot(path=str(shot))
        except Exception:
            pass
        raise CheckpointDetected(
            f"LinkedIn checkpoint/CAPTCHA detected ({reason}). "
            f"Screenshot saved to {shot}. Stopping to protect the account."
        )
