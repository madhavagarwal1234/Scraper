"""
B.L.A.S.T. Local Server — Layer 3 Tool
Serves the dashboard and handles API requests from the browser.

Endpoints:
  GET  /             → serves index.html
  GET  /api/scrape   → runs scraper, returns articles JSON
  GET  /api/articles → returns current .tmp/articles.json (cached)

Run with: python tools/serve.py
"""

import http.server
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from bs4 import BeautifulSoup
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / ".tmp"
ARTICLES_FILE = TMP_DIR / "articles.json"
PORT = 8000


class BLASTHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/scrape":
            self._handle_scrape()
        elif path == "/api/articles":
            self._handle_articles()
        elif path == "/api/read":
            self._handle_read(parsed.query)
        else:
            super().do_GET()

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _handle_scrape(self):
        print("\n[Server] /api/scrape called — running scraper...")
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            result = subprocess.run(
                [sys.executable, str(BASE_DIR / "tools" / "scraper.py")],
                capture_output=True, text=True, timeout=120, env=env,
                encoding="utf-8", errors="replace"
            )
            if result.returncode != 0:
                self._send_json({"error": result.stderr}, 500)
                return
            if ARTICLES_FILE.exists():
                with open(ARTICLES_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                self._send_json(data)
            else:
                self._send_json({"error": "No articles file generated."}, 500)
        except subprocess.TimeoutExpired:
            self._send_json({"error": "Scraper timed out after 120s."}, 504)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_articles(self):
        if ARTICLES_FILE.exists():
            with open(ARTICLES_FILE, encoding="utf-8") as f:
                data = json.load(f)
            self._send_json(data)
        else:
            self._send_json({"articles": [], "total_count": 0, "scraped_at": None})

    def _handle_read(self, query):
        qs = urllib.parse.parse_qs(query)
        url = qs.get("url", [""])[0]
        if not url:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing url parameter")
            return

        try:
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8', errors='replace')

            parsed_url = urllib.parse.urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            # --- BeautifulSoup Native Parsing ---
            soup = BeautifulSoup(html, "html.parser")
            
            title = "(No Title)"
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title = og_title["content"]
            elif soup.title:
                title = soup.title.string

            author = soup.find("meta", property="author")
            author_name = author["content"] if author and author.get("content") else ""

            # Locate core article payload
            main_node = soup.find("article") or soup.find("main")
            if not main_node:
                divs = soup.find_all("div")
                if divs:
                    main_node = max(divs, key=lambda d: len(d.find_all("p")))

            # Purge off-brand/spammy native nodes
            if main_node:
                for bad in main_node.find_all(["nav", "header", "footer", "aside", "form", "button", "script", "style", "iframe", "svg"]):
                    bad.decompose()
                
                # Deep Sanitize: Strip all classes, IDs, inline styles to force true Native Rendering
                for tag in main_node.find_all(True):
                    tag.attrs = {k: v for k, v in tag.attrs.items() if k in ['href', 'src', 'alt']}
                main_node.attrs = {}

            content_html = str(main_node) if main_node else "<p>Could not extract article content natively.</p>"

            # The Voxoby Native Reader UX
            reader_html = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
              <meta charset="UTF-8">
              <base href="{base_url}/">
              <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
              <style>
                :root {{
                  --bg: #0b0b1e;
                  --surface: #0f0f24;
                  --text: #f0f0ff;
                  --text-muted: #9090b8;
                  --accent: #7c5cfc;
                  --accent-dim: rgba(124,92,252,0.15);
                  --border: rgba(255,255,255,0.08);
                }}
                body {{
                  margin: 0; padding: 40px;
                  background: var(--bg); color: var(--text);
                  font-family: 'Inter', sans-serif;
                  line-height: 1.7; font-size: 17px;
                }}
                .reader-container {{
                  max-width: 720px; margin: 0 auto;
                  background: var(--surface);
                  padding: 40px 50px;
                  border-radius: 20px;
                  border: 1px solid var(--border);
                  box-shadow: 0 10px 40px rgba(0,0,0,0.5);
                }}
                h1 {{ font-size: 32px; font-weight: 700; color: #fff; margin-top: 0; line-height: 1.3; }}
                h2, h3 {{ color: #fff; margin-top: 40px; margin-bottom: 16px; }}
                p {{ color: var(--text); margin-bottom: 24px; }}
                a {{ color: var(--accent); text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
                img {{ max-width: 100%; height: auto; border-radius: 12px; margin: 24px 0; }}
                .meta {{ color: var(--text-muted); font-size: 14px; margin-bottom: 32px; font-weight: 500; display: flex; align-items: center; gap: 12px; }}
                .tag {{ background: var(--accent-dim); color: var(--accent); padding: 4px 10px; border-radius: 6px; }}
                .reader-container > * {{ max-width: 100%; }}
                ul, ol {{ margin-bottom: 24px; padding-left: 20px; }}
                li {{ margin-bottom: 10px; }}
                blockquote {{ border-left: 4px solid var(--accent); margin: 0; padding-left: 20px; font-style: italic; color: var(--text-muted); }}
                figure {{ margin: 0; }}
                figcaption {{ font-size: 13px; color: var(--text-muted); text-align: center; margin-top: 8px; }}
              </style>
            </head>
            <body>
              <div class="reader-container">
                <div class="meta">
                  <span class="tag">Voxoby Native Reader</span> {'<span>• By ' + author_name + '</span>' if author_name else ''}
                </div>
                <h1>{title}</h1>
                <hr style="border:none; border-top: 1px solid var(--border); margin: 30px 0;">
                <div class="content">
                  {content_html}
                </div>
              </div>
              <script>
                const targetLang = new URLSearchParams(window.location.search).get('lang');
                if (targetLang && targetLang !== 'en') {{
                  
                  const getCache = () => JSON.parse(localStorage.getItem('blast_translations') || '{{}}');
                  const saveCache = (lang, text, trans) => {{
                      const c = getCache();
                      c[`${{lang}}::${{text}}`] = trans;
                      localStorage.setItem('blast_translations', JSON.stringify(c));
                  }};

                  const translateText = async (text, lang) => {{
                    // Utilize free generic Google endpoint for heavy full-article body translation
                    const url = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=${{lang}}&dt=t&q=${{encodeURIComponent(text)}}`;
                    try {{
                      const res = await fetch(url);
                      const data = await res.json();
                      return data[0].map(x => x[0]).join('');
                    }} catch (e) {{ return text; }}
                  }};
                  
                  (async () => {{
                    const elements = document.querySelectorAll('.reader-container h1, .reader-container h2, .reader-container h3, .reader-container p, .reader-container li, .reader-container blockquote');
                    for (const el of elements) {{
                      const txt = el.innerText.trim();
                      if (txt.length > 2) {{
                        const cache = getCache();
                        const cacheKey = `${{targetLang}}::${{txt}}`;
                        if (cache[cacheKey]) {{
                          el.innerText = cache[cacheKey];
                        }} else {{
                          el.innerHTML = `<span style="opacity: 0.5;">✨ Translating...</span>`;
                          const translated = await translateText(txt, targetLang);
                          el.innerText = translated;
                          saveCache(targetLang, txt, translated);
                        }}
                      }}
                    }}
                  }})();
                }}
              </script>
            </body>
            </html>
            """

            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(reader_html.encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Native Reader error: {str(e)}".encode('utf-8'))

    def log_message(self, format, *args):
        print(f"  [HTTP] {self.address_string()} — {format % args}")


if __name__ == "__main__":
    print(f"\n[VOXOBY] Server starting on http://localhost:{PORT}")
    print(f"   Dashboard:    http://localhost:{PORT}/index.html")
    print(f"   Scrape API:   http://localhost:{PORT}/api/scrape")
    print(f"   Articles API: http://localhost:{PORT}/api/articles")
    print(f"   Press Ctrl+C to stop.\n")
    with http.server.HTTPServer(("", PORT), BLASTHandler) as httpd:
        httpd.serve_forever()
