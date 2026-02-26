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
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE = os.path.join(PROJECT_ROOT, "data", "telegram_queue.json")
CONTENT_DIR = os.path.join(PROJECT_ROOT, "content", "news")
SITE_URL = "https://konopla.ua"


def parse_frontmatter(filepath):
    """Парсить YAML frontmatter з .md файлу."""
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    # Extract frontmatter between --- markers
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

    # Parse categories
    cat_match = re.search(r'categories:\s*\["([^"]+)"\]', match.group(1))
    if cat_match:
        fm['category'] = cat_match.group(1)

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


def run():
    """Основна функція — постить все з черги."""
    from telegram_bot import send_photo, send_message, TELEGRAM_CHAT_ID

    if not TELEGRAM_CHAT_ID:
        print("[ERROR] TELEGRAM_CHAT_ID not set")
        return 1

    # Load queue
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

        filepath = os.path.join(CONTENT_DIR, filename)
        if not os.path.exists(filepath):
            print(f"   [WARN] File not found: {filename}")
            continue

        fm = parse_frontmatter(filepath)
        if fm.get('draft') == 'true':
            print(f"   [WARN] Article still draft: {filename}")
            continue

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
            posted += 1
        else:
            print(f"   [WARN] Failed to post: {filename}")

        # Delay between messages to avoid rate limits
        time.sleep(3)

    # Clear queue
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump({"articles": []}, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Posted {posted}/{len(articles)} articles to Telegram")
    return 0


if __name__ == "__main__":
    sys.exit(run())
