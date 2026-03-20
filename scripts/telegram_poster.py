"""
telegram_poster.py — Постить апрувлені статті в Telegram-канал.

Читає data/telegram_queue.json, для кожної статті:
1. Парсить .md файл (frontmatter)
2. Формує повідомлення
3. Надсилає з фото в канал
4. Очищує чергу
"""

import json
import os
import re
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE = os.path.join(PROJECT_ROOT, "data", "telegram_queue.json")
SOCIAL_STATUS_FILE = os.path.join(PROJECT_ROOT, "data", "social_status.json")
CONTENT_DIR = os.path.join(PROJECT_ROOT, "content", "news")
SITE_URL = "https://konopla.ua"


def parse_frontmatter(filepath):
    """Парсить YAML frontmatter з .md файлу."""
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    # Split on --- markers
    parts = text.split('---', 2)
    if len(parts) < 3:
        return {}

    fm = {}
    for line in parts[1].splitlines():
        if ':' not in line:
            continue
        key, _, val = line.partition(':')
        key = key.strip()
        val = val.strip()
        if not key:
            continue
        if val.startswith('['):
            # Array like categories: ["value"] — extract first element
            m = re.search(r'"([^"]+)"', val)
            if m:
                fm['category'] = m.group(1)
            fm[key] = val
        else:
            # Strip surrounding quotes if present
            fm[key] = val.strip('"\'')

    return fm


def build_telegram_message(fm, filename):
    """Формує повідомлення для Telegram-каналу."""
    title = fm.get('title', 'Нова стаття')
    summary = fm.get('summary', '')
    category = fm.get('category', 'інше')
    telegram_hook = fm.get('telegram_hook', '')

    # Emoji per category
    emoji_map = {
        "текстиль": "🧵", "будівництво": "🏗️", "агро": "🌱",
        "біопластик": "♻️", "автопром": "🚗", "харчова": "🥗",
        "енергетика": "⚡", "косметика": "✨", "законодавство": "📋",
        "наука": "🔬", "екологія": "🌍", "бізнес": "💼",
        "відео": "🎬", "інше": "📰",
    }
    emoji = emoji_map.get(category, "📰")

    slug = filename.replace('.md', '')
    article_url = f"{SITE_URL}/news/{slug}/"

    # Use telegram_hook if available, otherwise fall back to summary
    teaser = telegram_hook if telegram_hook else summary

    message = f"""{emoji} <b>{title}</b>

{teaser}

<a href="{article_url}">Читати повністю →</a>"""

    return message


def get_photo_path(fm):
    """Визначає шлях до фото для відправки."""
    image = fm.get('image', '')
    if not image:
        return None, None

    # Local Gemini-generated image
    if image.startswith('/images/generated/'):
        local_path = os.path.join(PROJECT_ROOT, "static", image.lstrip('/'))
        if os.path.exists(local_path):
            return local_path, None

    # External URL (Unsplash etc)
    if image.startswith('http'):
        return None, image

    return None, None


def _update_social_status(filename, platform, data=None):
    """Оновлює social_status.json після публікації."""
    from utils import load_json, save_json
    status = load_json(SOCIAL_STATUS_FILE, default={})
    if filename not in status:
        status[filename] = {}
    from datetime import datetime, timezone
    entry = {"posted_at": datetime.now(timezone.utc).isoformat()}
    if data:
        entry.update(data)
    status[filename][platform] = entry
    save_json(SOCIAL_STATUS_FILE, status)


def _post_single(filename, custom_text=None):
    """Постить одну статтю в Telegram. Повертає True/False."""
    from telegram_bot import send_photo, send_message, TELEGRAM_CHAT_ID

    if not TELEGRAM_CHAT_ID:
        print("[ERROR] TELEGRAM_CHAT_ID not set")
        return False

    filepath = os.path.join(CONTENT_DIR, filename)
    if not os.path.exists(filepath):
        print(f"   [WARN] File not found: {filename}")
        return False

    fm = parse_frontmatter(filepath)
    if fm.get('draft') == 'true':
        print(f"   [WARN] Article still draft: {filename}")
        return False

    if custom_text:
        # Build message with custom text
        slug = filename.replace('.md', '')
        article_url = f"{SITE_URL}/news/{slug}/"
        message = f"{custom_text}\n\n<a href=\"{article_url}\">Читати повністю →</a>"
    else:
        message = build_telegram_message(fm, filename)

    photo_path, photo_url = get_photo_path(fm)
    print(f"   📨 Posting: {fm.get('title', filename)[:60]}...")

    success = False
    if photo_path or photo_url:
        success = send_photo(
            photo_url=photo_url,
            caption=message,
            photo_path=photo_path
        )
    else:
        success = send_message(message)

    if success:
        _update_social_status(filename, "telegram")

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
    from telegram_bot import send_photo, send_message, TELEGRAM_CHAT_ID

    if not TELEGRAM_CHAT_ID:
        print("[ERROR] TELEGRAM_CHAT_ID not set")
        return 1

    if not os.path.exists(QUEUE_FILE):
        print("[INFO] No telegram queue file found")
        return 0

    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        queue = json.load(f)

    articles = queue.get("articles", [])
    if not articles:
        print("[INFO] Telegram queue is empty")
        return 0

    print(f"📨 Posting {len(articles)} articles to Telegram...")

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

    print(f"\n✅ Posted {posted}/{len(articles)} articles to Telegram")
    return 0


if __name__ == "__main__":
    sys.exit(run())
