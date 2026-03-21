# 📋 SOP: Newsletter & Reddit Scraper
> **Tool:** `tools/scraper.py`
> **Last Updated:** 2026-03-21
> **Layer:** 1 (Architecture)

---

## 🎯 Goal
Scrape the latest AI articles (last 24h) from Ben's Bites, The AI Rundown, and Reddit.
Output a structured JSON file to `.tmp/articles.json`.

---

## 📥 Inputs
- No user input required at runtime.
- Configuration via `.env` (if needed for auth).

## 📤 Outputs
- `.tmp/articles.json` — Full scraper output matching the Scraper Output schema in `gemini.md`.

---

## 🔧 Tool Logic (Per Source)

### Ben's Bites (bensbites.com)
- **Method:** HTTP GET to `https://www.bensbites.com/archive`
- **Parser:** BeautifulSoup — find `<a>` tags linking to `/p/` slugs
- **Date Filter:** Parse date from archive listing; skip if > 24h old
- **ID:** SHA-256 of normalized URL
- **Fallback:** If blocked by bot protection, log error and continue to next source

### The AI Rundown (therundown.ai)
- **Method:** HTTP GET to `https://www.therundown.ai/archive`
- **Parser:** BeautifulSoup — find issue links
- **Date Filter:** Parse date from page; skip if > 24h old
- **ID:** SHA-256 of normalized URL

### Reddit (JSON API)
- **Method:** GET `https://www.reddit.com/r/{sub}/new.json?limit=25`
- **Subreddits:** `artificial`, `MachineLearning`, `AINews`
- **Headers:** `User-Agent: blast-scraper/1.0`
- **Date Filter:** `created_utc` field; skip if > 86400s ago
- **Fields:** `title`, `url`, `selftext`, `created_utc`, `permalink`, `thumbnail`

---

## ⚠️ Edge Cases & Known Gotchas
- Ben's Bites is on Beehiiv — may have bot protection. Use descriptive User-Agent.
- Reddit rate limit: 10 req/min unauthenticated. Add `time.sleep(1)` between subreddit calls.
- `thumbnail` from Reddit may return `"self"` or `"default"` — treat these as `null`.
- Published dates may be in various formats — normalize everything to ISO8601 UTC.

---

## 🔄 Update History
| Date | Change | Reason |
|------|--------|--------|
| 2026-03-21 | SOP created | Initial build |
