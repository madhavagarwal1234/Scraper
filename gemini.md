# 📜 gemini.md — Project Constitution
> **Status:** ✅ APPROVED — Blueprint Confirmed
> **Last Updated:** 2026-03-21
> **Architect:** System Pilot (Voxoby Protocol)

---

## 🏛️ Architectural Invariants

1. **Data-First Rule:** No tool (`tools/`) may be written without a confirmed JSON schema here.
2. **LLMs are probabilistic; business logic is deterministic.** All decisions belong in `tools/`.
3. **Environment variables** are stored exclusively in `.env`. Never hardcoded.
4. **`.tmp/`** is ephemeral. All intermediate files land there. Never committed.
5. **`architecture/`** SOPs must be updated *before* any code change to `tools/`.
6. A project is only **"Complete"** when the final Payload reaches its cloud destination.
7. **Self-Annealing:** Every error → logged in `progress.md` → fixed → SOP updated in `architecture/`.
8. **Supabase** is the future cloud backend. Phase 1 uses `localStorage` as source of truth.

---

## 🗂️ Data Schema (CONFIRMED ✅)

### Article Object (Core Entity)
```json
{
  "id": "string (SHA-256 hash of normalized URL)",
  "source": "bensbites | airundown | reddit",
  "source_label": "string (e.g. \"Ben's Bites\")",
  "title": "string",
  "summary": "string (first 300 chars of article body, or excerpt)",
  "url": "string (canonical link to article)",
  "published_at": "ISO8601 datetime (e.g. 2026-03-21T00:00:00Z)",
  "scraped_at": "ISO8601 datetime",
  "tags": ["string"],
  "saved": "boolean (default: false)",
  "thumbnail": "string | null (image URL if available)"
}
```

### Scraper Output (`.tmp/articles.json`)
```json
{
  "scraped_at": "ISO8601 datetime",
  "sources_scraped": ["bensbites", "airundown", "reddit"],
  "articles": [Article],
  "total_count": "integer",
  "errors": []
}
```

### localStorage Schema (Browser Source of Truth)
```json
{
  "blast_articles": "[Article]  (all fetched articles, stringified)",
  "blast_saved": "[string]    (array of saved article IDs)",
  "blast_last_fetch": "ISO8601 datetime (last successful scrape timestamp)"
}
```

---

## 🔧 Behavioral Rules (CONFIRMED ✅)

| Rule ID | Rule | Notes |
|---------|------|-------|
| BR-001 | Only show articles published within the last 24 hours | Filter on `published_at` |
| BR-002 | If no new articles since last fetch, show existing cache silently | No error shown |
| BR-003 | Saved articles persist across page refreshes via `localStorage` | `blast_saved` array |
| BR-004 | All scraped data persists in `localStorage` between sessions | `blast_articles` key |
| BR-005 | Scraper runs on demand + can be scheduled every 24h via Windows Task Scheduler | `tools/run_scraper.py` |
| BR-006 | Design must be gorgeous, interactive, and visually premium | Glassmorphism + dark mode |
| BR-007 | Supabase integration deferred to Phase 2 | Use `localStorage` for now |
| BR-008 | Reddit subreddits: r/artificial, r/MachineLearning, r/AINews | Filter for last 24h posts |

---

## 🔗 Integrations Registry

| Service | Purpose | Endpoint | Status |
|---------|---------|----------|--------|
| Ben's Bites | Newsletter scrape | `https://www.bensbites.com/archive` | 🟡 To Verify |
| The AI Rundown | Newsletter scrape | `https://www.therundown.ai/archive` | 🟡 To Verify |
| Reddit JSON API | Subreddit posts | `https://www.reddit.com/r/{sub}/new.json` | 🟡 To Verify |
| Supabase | Cloud DB (Phase 2) | TBD | 🔴 Deferred |

---

## 🗺️ Maintenance Log

| Date       | Change Made                          | Author |
|------------|--------------------------------------|--------|
| 2026-03-21 | Project initialized                  | System Pilot |
| 2026-03-21 | Blueprint confirmed, schema locked   | System Pilot |
