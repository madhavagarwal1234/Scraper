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

if not os.path.exists(TMP_DIR):
    try:
        os.makedirs(TMP_DIR, exist_ok=True)
    except:
        pass

app = Flask(__name__)

# --- New Route for "/" to serve index.html directly from Python ---
@app.route('/')
def home():
    try:
        with open(os.path.join(BASE_DIR, 'index.html'), 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error loading index.html: {str(e)}", 500

@app.route('/api/scrape')
def handle_scrape():
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
        return jsonify({"articles": [], "total_count": 0, "scraped_at": None})

@app.route('/api/read')
def handle_read():
    url = request.args.get('url', '')
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

        # Reader Template
        reader_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <base href="{base_url}/">
          <style>
            :root {{ --bg: #0b0b1e; --surface: #0f0f24; --text: #f0f0ff; --text-muted: #9090b8; --accent: #7c5cfc; --border: rgba(255,255,255,0.08); }}
            body {{ margin: 0; padding: 40px; background: var(--bg); color: var(--text); font-family: sans-serif; line-height: 1.7; font-size: 17px; }}
            .reader-container {{ max-width: 720px; margin: 0 auto; background: var(--surface); padding: 40px 50px; border-radius: 20px; border: 1px solid var(--border); }}
            h1 {{ font-size: 32px; font-weight: 700; color: #fff; margin-top: 0; }}
            p {{ color: var(--text); margin-bottom: 24px; }}
            .tag {{ background: rgba(124,92,252,0.15); color: var(--accent); padding: 4px 10px; border-radius: 6px; }}
          </style>
        </head>
        <body>
          <div class="reader-container">
            <div class="meta"><span class="tag">Voxoby Native Reader</span></div>
            <h1>{title}</h1>
            <div class="content">{content_html}</div>
          </div>
        </body>
        </html>
        """
        return Response(reader_html, mimetype='text/html')
    except Exception as e:
        return f"Native Reader error: {str(e)}", 500

if __name__ == "__main__":
    app.run()
