"""
Voxoby Scraper — Layer 3 Tool
Fetches AI news from Ben's Bites, The AI Rundown, and Reddit. (r/artificial, r/MachineLearning, r/AINews)
Output: .tmp/articles.json

SOP Reference: architecture/scraper_sop.md
Schema Reference: gemini.md
"""

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Force UTF-8 output so emojis don't crash on Windows cp1252 terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / ".tmp"
TMP_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = TMP_DIR / "articles.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36 blast-scraper/1.0"
    )
}
CUTOFF = datetime.now(timezone.utc) - timedelta(hours=24)


# ── Helpers ───────────────────────────────────────────────────────────────────
def make_id(url: str) -> str:
    """SHA-256 hash of a normalized URL."""
    return hashlib.sha256(url.strip().lower().encode()).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_within_24h(dt: datetime) -> bool:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt >= CUTOFF


def safe_thumbnail(thumb: str | None) -> str | None:
    if not thumb or thumb in ("self", "default", "nsfw", "spoiler", "image"):
        return None
    if thumb.startswith("http"):
        return thumb
    return None


# ── Scrapers ──────────────────────────────────────────────────────────────────

def scrape_bensbites() -> tuple[list[dict], list[str]]:
    articles, errors = [], []
    url = "https://www.bensbites.com/archive"
    print(f"  [Ben's Bites] Fetching {url} ...")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Beehiiv archive: posts are in <a> tags with href containing /p/
        links = soup.find_all("a", href=True)
        seen = set()
        for a in links:
            href = a["href"]
            if "/p/" not in href:
                continue
            # Normalize URL
            if href.startswith("/"):
                href = "https://www.bensbites.com" + href
            if href in seen:
                continue
            seen.add(href)

            title_el = a.get_text(strip=True)
            if not title_el or len(title_el) < 5:
                continue

            # Try to find date nearby
            pub_date = None
            parent = a.find_parent()
            if parent:
                date_el = parent.find(["time", "span"], class_=lambda c: c and "date" in c.lower())
                if date_el and date_el.get("datetime"):
                    try:
                        pub_date = datetime.fromisoformat(date_el["datetime"].replace("Z", "+00:00"))
                    except ValueError:
                        pass
                if not pub_date and date_el:
                    try:
                        pub_date = datetime.strptime(date_el.get_text(strip=True), "%B %d, %Y")
                        pub_date = pub_date.replace(tzinfo=timezone.utc)
                    except ValueError:
                        pass

            # If we cannot determine the date, include it (we're on the archive page so recent)
            if pub_date and not is_within_24h(pub_date):
                continue

            # If pub_date is unknown, default to now (conservative approach for archive page)
            if pub_date is None:
                pub_date = datetime.now(timezone.utc)

            articles.append({
                "id": make_id(href),
                "source": "bensbites",
                "source_label": "Ben's Bites",
                "title": title_el[:200],
                "summary": "",
                "url": href,
                "published_at": pub_date.isoformat(),
                "scraped_at": now_iso(),
                "tags": ["AI", "newsletter"],
                "saved": False,
                "thumbnail": None,
            })
            if len(articles) >= 10:
                break

        def fetch_og(a_dict):
            try:
                p_resp = requests.get(a_dict["url"], headers=HEADERS, timeout=5)
                if p_resp.status_code == 200:
                    p_soup = BeautifulSoup(p_resp.text, "html.parser")
                    og_img = p_soup.find("meta", property="og:image")
                    if og_img and og_img.get("content"):
                        a_dict["thumbnail"] = og_img["content"]
                    og_desc = p_soup.find("meta", property="og:description")
                    if og_desc and og_desc.get("content"):
                        a_dict["summary"] = og_desc["content"][:300]
            except Exception:
                pass

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=10) as executor:
            list(executor.map(fetch_og, articles))

        print(f"  [Ben's Bites] Found {len(articles)} articles.")
    except Exception as e:
        msg = f"Ben's Bites scrape failed: {e}"
        print(f"  [ERROR] {msg}")
        errors.append(msg)
    return articles, errors


def scrape_airundown() -> tuple[list[dict], list[str]]:
    articles, errors = [], []
    url = "https://www.therundown.ai/archive"
    print(f"  [AI Rundown] Fetching {url} ...")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        seen = set()
        # Look for issue/post links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # therundown.ai typically uses /p/ or /issues/ paths
            if not any(p in href for p in ["/p/", "/issues/", "/newsletter/"]):
                continue
            if href.startswith("/"):
                href = "https://www.therundown.ai" + href
            if not href.startswith("http"):
                continue
            if href in seen:
                continue
            seen.add(href)

            # Better parsing from verified HTML structure (a tags contain h3 titles)
            h3 = a.find("h3")
            if h3:
                title_text = h3.get_text(strip=True)
            else:
                title_text = a.get_text(strip=True)

            if not title_text or len(title_text) < 5:
                continue

            # Date detection
            pub_date = None
            parent = a.find_parent()
            if parent:
                time_el = parent.find("time")
                if time_el and time_el.get("datetime"):
                    try:
                        pub_date = datetime.fromisoformat(time_el["datetime"].replace("Z", "+00:00"))
                    except ValueError:
                        pass

            if pub_date and not is_within_24h(pub_date):
                continue
            if pub_date is None:
                pub_date = datetime.now(timezone.utc)

            articles.append({
                "id": make_id(href),
                "source": "airundown",
                "source_label": "The AI Rundown",
                "title": title_text[:200],
                "summary": "",
                "url": href,
                "published_at": pub_date.isoformat(),
                "scraped_at": now_iso(),
                "tags": ["AI", "newsletter"],
                "saved": False,
                "thumbnail": None,
            })
            if len(articles) >= 10:
                break

        def fetch_og_ar(a_dict):
            try:
                p_resp = requests.get(a_dict["url"], headers=HEADERS, timeout=5)
                if p_resp.status_code == 200:
                    p_soup = BeautifulSoup(p_resp.text, "html.parser")
                    og_img = p_soup.find("meta", property="og:image")
                    if og_img and og_img.get("content"):
                        a_dict["thumbnail"] = og_img["content"]
                    og_desc = p_soup.find("meta", property="og:description")
                    if og_desc and og_desc.get("content"):
                        a_dict["summary"] = og_desc["content"][:300]
            except Exception:
                pass

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=10) as executor:
            list(executor.map(fetch_og_ar, articles))

        print(f"  [AI Rundown] Found {len(articles)} articles.")
    except Exception as e:
        msg = f"AI Rundown scrape failed: {e}"
        print(f"  [ERROR] {msg}")
        errors.append(msg)
    return articles, errors


def scrape_reddit() -> tuple[list[dict], list[str]]:
    articles, errors = [], []
    subreddits = ["artificial", "MachineLearning", "AINews"]

    for sub in subreddits:
        api_url = f"https://www.reddit.com/r/{sub}/new.json?limit=25"
        print(f"  [Reddit] Fetching r/{sub} ...")
        try:
            resp = requests.get(api_url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            posts = data.get("data", {}).get("children", [])

            for post in posts:
                p = post.get("data", {})
                created_utc = p.get("created_utc", 0)
                pub_date = datetime.fromtimestamp(created_utc, tz=timezone.utc)

                if not is_within_24h(pub_date):
                    continue

                title = p.get("title", "").strip()
                post_url = p.get("url", "")
                permalink = "https://www.reddit.com" + p.get("permalink", "")
                selftext = p.get("selftext", "")
                summary = selftext[:300] if selftext and selftext != "[removed]" else f"Posted in r/{sub}"
                thumb = safe_thumbnail(p.get("thumbnail"))

                articles.append({
                    "id": make_id(permalink),
                    "source": "reddit",
                    "source_label": f"r/{sub}",
                    "title": title[:200],
                    "summary": summary,
                    "url": post_url if post_url else permalink,
                    "published_at": pub_date.isoformat(),
                    "scraped_at": now_iso(),
                    "tags": ["AI", "reddit", sub],
                    "saved": False,
                    "thumbnail": thumb,
                })

            sub_count = sum(1 for a in articles if isinstance(a.get('tags'), list) and sub in a['tags'])
            print(f"  [Reddit] r/{sub}: found {sub_count} posts.")
            time.sleep(1)  # Rate limit courtesy

        except Exception as e:
            msg = f"Reddit r/{sub} scrape failed: {e}"
            print(f"  [ERROR] {msg}")
            errors.append(msg)

    return articles, errors


# ── Main ──────────────────────────────────────────────────────────────────────
def run():
    print("\n[VOXOBY] Scraper Starting...")
    print(f"   Cutoff: {CUTOFF.isoformat()}")
    print(f"   Output: {OUTPUT_FILE}\n")

    all_articles: list[dict] = []
    all_errors: list[str] = []
    sources_scraped: list[str] = []

    # Ben's Bites
    bb_articles, bb_errors = scrape_bensbites()
    all_articles.extend(bb_articles)
    all_errors.extend(bb_errors)
    if not bb_errors:
        sources_scraped.append("bensbites")

    # AI Rundown
    ar_articles, ar_errors = scrape_airundown()
    all_articles.extend(ar_articles)
    all_errors.extend(ar_errors)
    if not ar_errors:
        sources_scraped.append("airundown")

    # Reddit
    rd_articles, rd_errors = scrape_reddit()
    all_articles.extend(rd_articles)
    all_errors.extend(rd_errors)
    if not rd_errors:
        sources_scraped.append("reddit")

    # Deduplicate by ID
    seen_ids = set()
    unique_articles = []
    for a in all_articles:
        if a["id"] not in seen_ids:
            seen_ids.add(a["id"])
            unique_articles.append(a)

    # Sort by published_at descending
    unique_articles.sort(key=lambda x: x["published_at"], reverse=True)

    output = {
        "scraped_at": now_iso(),
        "sources_scraped": sources_scraped,
        "articles": unique_articles,
        "total_count": len(unique_articles),
        "errors": all_errors,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n[VOXOBY] Scrape complete!")
    print(f"   Total articles: {len(unique_articles)}")
    print(f"   Sources scraped: {sources_scraped}")
    if all_errors:
        print(f"   [WARN] Errors ({len(all_errors)}): {all_errors}")
    print(f"   Saved to: {OUTPUT_FILE}\n")

    return output


if __name__ == "__main__":
    run()
