"""Launch / teardown of a persistent Camoufox browser context.

`persistent_context=True` + `user_data_dir` keep the LinkedIn/Google session on
disk, so the human-in-the-loop login only happens on the first run.
"""

from __future__ import annotations

from camoufox.sync_api import Camoufox

from .config import Settings


class BrowserManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cm = None
        self.ctx = None  # Playwright persistent BrowserContext

    def launch(self):
        """Open Camoufox. Falls back to geoip=False if a geoip launch fails."""
        s = self.settings
        try:
            return self._open(geoip=s.geoip)
        except Exception as exc:  # noqa: BLE001 - we want a robust first run
            if s.geoip:
                print(
                    f"[browser] geoip launch failed ({exc!r}); retrying without geoip.",
                    flush=True,
                )
                self.close()
                return self._open(geoip=False)
            raise

    def _open(self, geoip: bool):
        s = self.settings
        kwargs = dict(
            headless=False,
            humanize=s.humanize,
            os=s.os_name,
            persistent_context=True,
            user_data_dir=str(s.profile_dir),
            geoip=geoip,
        )
        kwargs["locale"] = s.locale  # always set; geoip still controls timezone/geo
        if s.proxy:
            kwargs["proxy"] = s.proxy

        self._cm = Camoufox(**kwargs)
        self.ctx = self._cm.__enter__()
        # A persistent context usually opens with one blank page; reuse it.
        page = self.ctx.pages[0] if getattr(self.ctx, "pages", None) else self.ctx.new_page()
        page.set_default_timeout(30_000)
        # Swallow page-level JS errors so LinkedIn's noisy console can't crash us.
        try:
            self.ctx.on("pageerror", lambda e: None)
            page.on("pageerror", lambda e: None)
        except Exception:
            pass
        return page

    def close(self) -> None:
        if self._cm is not None:
            try:
                self._cm.__exit__(None, None, None)
            except Exception:  # noqa: BLE001 - best-effort teardown
                pass
            finally:
                self._cm = None
                self.ctx = None
