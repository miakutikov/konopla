#!/usr/bin/env python3
"""
moderator.py — Обробляє рішення адміна з Telegram.
Опитує getUpdates, для схвалених статей: створює Hugo файли + постить в канал.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import PENDING_FILE, TELEGRAM_OFFSET_FILE, PENDING_MAX_AGE_HOURS, API_DELAY_SECONDS
from telegram_bot import (
    get_updates, answer_callback_query, edit_message_reply_markup,
    send_message, send_photo, ADMIN_CHAT_ID
)
from publisher import create_article_file, create_telegram_message


def load_json(filepath, default):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def run_moderator():
    print("=" * 60)
    print("🔍 KONOPLA.UA — Moderator")
    print("=" * 60)

    # Load pending articles
    pending = load_json(PENDING_FILE, {"articles": []})
    if not pending["articles"]:
        print("[INFO] No pending articles. Done.")
        save_result(0)
        return 0

    pending_map = {a["id"]: a for a in pending["articles"] if a.get("status") == "pending"}
    print(f"[INFO] {len(pending_map)} pending articles")

    # Load Telegram offset
    offset_data = load_json(TELEGRAM_OFFSET_FILE, {"offset": 0})
    offset = offset_data.get("offset", 0)

    # Poll Telegram for callback_query updates
    updates = get_updates(offset=offset)
    print(f"[INFO] Got {len(updates)} Telegram updates")

    approved_ids = []
    rejected_ids = []

    for update in updates:
        update_id = update.get("update_id", 0)
        offset = max(offset, update_id + 1)

        callback = update.get("callback_query")
        if not callback:
            continue

        callback_id = callback.get("id")
        data = callback.get("data", "")
        message = callback.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")

        if data.startswith("approve_"):
            article_id = data.replace("approve_", "")
            if article_id in pending_map:
                approved_ids.append(article_id)
                answer_callback_query(callback_id, "✅ Схвалено!")
            else:
                answer_callback_query(callback_id, "⚠️ Стаття не знайдена")
            if chat_id and message_id:
                edit_message_reply_markup(chat_id, message_id)

        elif data.startswith("reject_"):
            article_id = data.replace("reject_", "")
            rejected_ids.append(article_id)
            answer_callback_query(callback_id, "❌ Відхилено")
            if chat_id and message_id:
                edit_message_reply_markup(chat_id, message_id)

    # Save updated offset
    save_json(TELEGRAM_OFFSET_FILE, {"offset": offset})

    # Process approved articles
    content_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "content", "news"
    )

    published_count = 0
    for article_id in approved_ids:
        article = pending_map.get(article_id)
        if not article:
            continue

        rewritten = article.get("rewritten", {})
        source_url = article.get("source_url", "")
        source_name = article.get("source_name", "")
        image_data = article.get("image_data")

        print(f"\n📰 Publishing: {rewritten.get('title', '?')[:60]}...")

        # Create Hugo file
        filepath = create_article_file(
            article_data=rewritten,
            source_url=source_url,
            source_name=source_name,
            image_data=image_data,
            content_dir=content_dir
        )

        if not filepath:
            print(f"   ❌ Failed to create file for {article_id}")
            continue

        # Post to Telegram channel
        try:
            tg_message = create_telegram_message(rewritten)
            if image_data:
                local_path = image_data.get("local_path", "")
                img_url = image_data.get("url", "")
                is_gemini = image_data.get("source") == "gemini"
                if is_gemini and local_path:
                    send_photo(photo_path=local_path, caption=tg_message)
                elif img_url and not img_url.startswith("/"):
                    send_photo(photo_url=img_url, caption=tg_message)
                else:
                    send_message(tg_message)
            else:
                send_message(tg_message)
        except Exception as e:
            print(f"   ⚠️ Telegram channel error: {e}")

        published_count += 1

        if published_count < len(approved_ids):
            time.sleep(API_DELAY_SECONDS)

    # Update pending: remove approved and rejected
    processed_ids = set(approved_ids) | set(rejected_ids)

    # Also clean up stale articles (>48h old)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=PENDING_MAX_AGE_HOURS)
    remaining = []
    for article in pending["articles"]:
        if article["id"] in processed_ids:
            continue
        created = article.get("created_at", "")
        try:
            created_dt = datetime.fromisoformat(created)
            if created_dt < cutoff:
                print(f"[INFO] Expired: {article.get('rewritten', {}).get('title', '?')[:50]}")
                continue
        except (ValueError, TypeError):
            pass
        remaining.append(article)

    pending["articles"] = remaining
    save_json(PENDING_FILE, pending)

    print(f"\n{'='*60}")
    print(f"✅ Published: {published_count}")
    print(f"❌ Rejected: {len(rejected_ids)}")
    print(f"⏳ Still pending: {len(remaining)}")
    print(f"{'='*60}")

    save_result(published_count)
    return 0


def save_result(approved_count):
    """Зберігає результат для GitHub Actions output."""
    result_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "moderate_result.json"
    )
    save_json(result_file, {"approved": approved_count})


if __name__ == "__main__":
    sys.exit(run_moderator())
