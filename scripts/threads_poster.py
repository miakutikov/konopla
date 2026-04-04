"""
threads_poster.py — Постить апрувлені статті в Threads (Meta/Instagram).

Threads Publishing API (2-step):
1. POST /threads — create media container
2. POST /threads_publish — publish the container

Потрібні secrets: THREADS_ACCESS_TOKEN, THREADS_USER_ID
"""

import json
import os
import re
import sys
import tempfile
import time
import urllib.request
import urllib.error
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE = os.path.join(PROJECT_ROOT, "data", "threads_queue.json")
SOCIAL_STATUS_FILE = os.path.join(PROJECT_ROOT, "data", "social_status.json")
CONTENT_DIR = os.path.join(PROJECT_ROOT, "content", "news")
SITE_URL = "https://konopla.ua"

THREADS_API = "https://graph.threads.net/v1.0"
THREADS_USER_ID = os.environ.get("THREADS_USER_ID", "")
THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "")


def parse_frontmatter(filepath):
    """Парсить YAML frontmatter з .md файлу."""
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    match = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
    if not match:
        return {}

    fm = {}
    for line in match.group(1).split('\n'):
        # Parse key: "quoted value" (greedy inside quotes)
        m = re.match(r'^(\w+):\s*"(.*)"\s*$', line)
        if m:
            fm[m.group(1)] = m.group(2)
        else:
            # Parse key: unquoted value (skip arrays like [...])
            m = re.match(r'^(\w+):\s*(.+?)\s*$', line)
            if m and not m.group(2).startswith('['):
                fm[m.group(1)] = m.group(2).strip("'").strip('"')

    cat_match = re.search(r'categories:\s*\["([^"]+)"\]', match.group(1))
    if cat_match:
        fm['category'] = cat_match.group(1)

    return fm


def build_threads_post(fm, filename):
    """Формує короткий пост для Threads."""
    title = fm.get('title', '')
    summary = fm.get('summary', '')
    category = fm.get('category', '')

    slug = filename.replace('.md', '')
    article_url = f"{SITE_URL}/news/{slug}/"

    # Use threads_hook if available (from Gemini), otherwise use summary
    hook = fm.get('threads_hook', '')
    if not hook:
        # Create a short teaser from summary (max ~200 chars)
        hook = summary[:200] if summary else title

    # Build post text (Threads max 500 chars)
    hashtags = f"#коноплі #{category}" if category else "#коноплі"

    suffix = f"\n\nДеталі: {article_url}\n\n{hashtags}"
    max_hook = 500 - len(suffix)
    hook_trimmed = hook[:max_hook] if len(hook) > max_hook else hook

    return f"{hook_trimmed}{suffix}"


def create_threads_container(text):
    """Step 1: Create media container."""
    url = f"{THREADS_API}/{THREADS_USER_ID}/threads"

    payload = {
        "media_type": "TEXT",
        "text": text,
        "access_token": THREADS_ACCESS_TOKEN,
    }

    data = urllib.parse.urlencode(payload).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return result.get("id")
    except Exception as e:
        print(f"   [ERROR] Threads container creation failed: {e}")
        return None


def publish_threads_container(container_id):
    """Step 2: Publish the container."""
    url = f"{THREADS_API}/{THREADS_USER_ID}/threads_publish"

    payload = {
        "creation_id": container_id,
        "access_token": THREADS_ACCESS_TOKEN,
    }

    data = urllib.parse.urlencode(payload).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return result.get("id") is not None
    except Exception as e:
        print(f"   [ERROR] Threads publish failed: {e}")
        return False


def _update_social_status(filename, platform, data=None):
    """Оновлює social_status.json після публікації."""
    from utils import load_json, save_json
    from datetime import datetime, timezone as tz
    status = load_json(SOCIAL_STATUS_FILE, default={})
    if filename not in status:
        status[filename] = {}
    entry = {"posted_at": datetime.now(tz.utc).isoformat()}
    if data:
        entry.update(data)
    status[filename][platform] = entry
    save_json(SOCIAL_STATUS_FILE, status)


def _post_single(filename, custom_text=None):
    """Постить одну статтю в Threads. Повертає True/False."""
    if not THREADS_USER_ID or not THREADS_ACCESS_TOKEN:
        print("[ERROR] THREADS_USER_ID or THREADS_ACCESS_TOKEN not set")
        return False

    filepath = os.path.join(CONTENT_DIR, filename)
    if not os.path.exists(filepath):
        print(f"   [WARN] File not found: {filename}")
        return False

    fm = parse_frontmatter(filepath)

    if custom_text:
        slug = filename.replace('.md', '')
        article_url = f"{SITE_URL}/news/{slug}/"
        suffix = f"\n\nДеталі: {article_url}\n\n#коноплі"
        max_text = 500 - len(suffix)
        text = (custom_text[:max_text] if len(custom_text) > max_text else custom_text) + suffix
    else:
        text = build_threads_post(fm, filename)

    print(f"   🧵 Posting: {fm.get('title', filename)[:60]}...")

    container_id = create_threads_container(text)
    if not container_id:
        return False

    time.sleep(5)

    success = publish_threads_container(container_id)
    if success:
        _update_social_status(filename, "threads")
        print(f"   ✅ Published to Threads")

    return success


def run():
    """Основна функція — постить все з черги або одну статтю."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--article", default="", help="Filename of single article to post")
    parser.add_argument("--text", default="", help="Custom text for the post")
    args, _ = parser.parse_known_args()

    # Per-article mode
    if args.article:
        success = _post_single(args.article, custom_text=args.text or None)
        return 0 if success else 1

    # Batch mode (existing queue)
    if not THREADS_USER_ID or not THREADS_ACCESS_TOKEN:
        print("[ERROR] THREADS_USER_ID or THREADS_ACCESS_TOKEN not set")
        return 1

    if not os.path.exists(QUEUE_FILE):
        print("[INFO] No threads queue file found")
        return 0

    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        queue = json.load(f)

    articles = queue.get("articles", [])
    if not articles:
        print("[INFO] Threads queue is empty")
        return 0

    print(f"🧵 Posting {len(articles)} articles to Threads...")

    posted = 0
    for item in articles:
        filename = item.get("filename", "")
        if not filename:
            continue

        if _post_single(filename):
            posted += 1

        time.sleep(3)

    # Clear queue atomically
    dirpath = os.path.dirname(QUEUE_FILE)
    with tempfile.NamedTemporaryFile(
        "w", dir=dirpath, delete=False, suffix=".tmp", encoding="utf-8"
    ) as f:
        json.dump({"articles": []}, f, ensure_ascii=False, indent=2)
        tmp_path = f.name
    os.replace(tmp_path, QUEUE_FILE)

    print(f"\n✅ Posted {posted}/{len(articles)} articles to Threads")
    return 0


if __name__ == "__main__":
    sys.exit(run())
