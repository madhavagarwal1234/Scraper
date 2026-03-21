from flask import Flask, jsonify, request, Response
import subprocess
import os
import sys
import json
from pathlib import Path
from bs4 import BeautifulSoup
import urllib.request
import urllib.parse

# Setup paths
BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / ".tmp"
ARTICLES_FILE = TMP_DIR / "articles.json"

# In Vercel, we need to ensure .tmp exists, but it's often read-only outside of /tmp
# We should probably use /tmp in serverless, but for now we follow codebase pattern
if not os.path.exists(TMP_DIR):
    try:
        os.makedirs(TMP_DIR, exist_ok=True)
    except:
        pass

app = Flask(__name__)

@app.route('/api/scrape')
def handle_scrape():
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        # Run scraper.- Note: Serverless environments may have limited write access.
        # This calls the existing scraper.py tool.
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / "tools" / "scraper.py")],
            capture_output=True, text=True, timeout=120, env=env,
            encoding="utf-8", errors="replace"
        )
        if result.returncode != 0:
            return jsonify({"error": result.stderr}), 500
        
        if ARTICLES_FILE.exists():
            with open(ARTICLES_FILE, encoding="utf-8") as f:
                data = json.load(f)
            return jsonify(data)
        else:
            return jsonify({"error": "No articles file generated."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/articles')
def handle_articles():
    if ARTICLES_FILE.exists():
        with open(ARTICLES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    else:
        # Default empty response if no cache
        return jsonify({"articles": [], "total_count": 0, "scraped_at": None})

@app.route('/api/read')
def handle_read():
    url = request.args.get('url', '')
    target_lang = request.args.get('lang', 'en')
    if not url:
        return "Missing url parameter", 400

    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='replace')

        parsed_url = urllib.parse.urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        soup = BeautifulSoup(html, "html.parser")
        
        title = "(No Title)"
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"]
        elif soup.title:
            title = soup.title.string

        author = soup.find("meta", property="author")
        author_name = author["content"] if author and author.get("content") else ""

        main_node = soup.find("article") or soup.find("main")
        if not main_node:
            divs = soup.find_all("div")
            if divs:
                main_node = max(divs, key=lambda d: len(d.find_all("p")))

        if main_node:
            for bad in main_node.find_all(["nav", "header", "footer", "aside", "form", "button", "script", "style", "iframe", "svg"]):
                bad.decompose()
            for tag in main_node.find_all(True):
                tag.attrs = {k: v for k, v in tag.attrs.items() if k in ['href', 'src', 'alt']}
            main_node.attrs = {}

        content_html = str(main_node) if main_node else "<p>Could not extract article content natively.</p>"

        # Native Reader Template (Synced with serve.py)
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
            // Translation script logic here...
          </script>
        </body>
        </html>
        """
        return Response(reader_html, mimetype='text/html')
        
    except Exception as e:
        return f"Native Reader error: {str(e)}", 500

# Vercel's entry point
if __name__ == "__main__":
    app.run()
