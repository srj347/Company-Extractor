# LinkedIn Company-Search Scraper (Camoufox)

Extracts **Company Name, Industry, Headquarter Location** from a LinkedIn company-search
results page (filtered by HQ location) into an Excel file. Built on
[Camoufox](https://github.com/daijro/camoufox) (anti-detect Firefox) with a **human-in-the-loop**
Google sign-in. The login session is persisted, so you only sign in once.

## Why Camoufox
Camoufox spoofs the browser fingerprint at the C++ level and drives Firefox via the Juggler
protocol (not CDP), so the automation is invisible to page JavaScript. It handles the
*fingerprint* detection vector. The *behavioral* vector (rate, dwell time, robotic pagination)
is handled here by human-like pacing, a persistent logged-in profile, and stopping on any
checkpoint.

## Setup

```bash
# from this folder (the project root)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m camoufox fetch          # one-time browser download (~150 MB)
```

> **Python version:** if `pip install` fails on a very new Python (e.g. 3.14), create the
> venv with Python 3.12 instead:
> ```bash
> brew install python@3.12
> $(brew --prefix python@3.12)/bin/python3.12 -m venv .venv && source .venv/bin/activate
> pip install -r requirements.txt && python -m camoufox fetch
> ```

## Run

```bash
python -m linkedin_company_scraper.main --pages 1     # scrape 1 page (first run: log in by hand)
python -m linkedin_company_scraper.main --pages 5     # scrape 5 pages (resumes from checkpoint)
python -m linkedin_company_scraper.main --fresh --pages 3
```

On the first run a Firefox window opens. **Click "Sign in with Google" and complete login**
(plus any 2FA). The script continues automatically once your feed loads and saves the session
to `profile/`, so later runs skip the login.

Output: **`companies.xlsx`**. Progress checkpoint: `checkpoint.json`.

## CLI options
| Flag | Meaning |
|------|---------|
| `--pages N` | Number of result pages to scrape (overrides `MAX_PAGES`). |
| `--start-page N` | Start from a specific page. |
| `--url URL` | Override the search URL. |
| `--out FILE` | Output `.xlsx` path. |
| `--fresh` | Ignore the checkpoint and start over. |

## Configuration (`.env`, optional)
Copy `.env.example` to `.env`. Leave the proxy commented out to use your normal IP; set
`PROXY_SERVER/USERNAME/PASSWORD` to route through a residential/ISP proxy later.

## Project layout
```
linkedin_company_scraper/
  config.py      settings + .env loading
  models.py      Company dataclass
  browser.py     Camoufox persistent-context launch
  auth.py        human-in-the-loop Google login
  navigator.py   goto / scroll / paginate
  extractor.py   parse name + industry + HQ from each card  <- tweak if LinkedIn changes markup
  detection.py   checkpoint/CAPTCHA guard (stops the run)
  storage.py     incremental Excel writer + resume checkpoint
  main.py        orchestrator + CLI
```

## Important notes
- Scraping LinkedIn is against its User Agreement; accounts doing it can be rate-limited or
  restricted. Keep volume low. The scraper **stops immediately** on a CAPTCHA/checkpoint
  (it saves a screenshot to `screenshots/` and flushes data already collected).
- Selectors in `extractor.py` are best-effort because LinkedIn rotates its CSS class names;
  they may need a small adjustment when run against the live DOM.
```
