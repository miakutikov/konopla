#!/usr/bin/env python3
"""
moderator.py — Обробляє рішення адміна з Telegram + команди бота.

Команди:
  /run     — запустити pipeline (збір новин)
  /status  — статус pending статей
  /help    — список команд
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import PENDING_FILE, TELEGRAM_OFFSET_FILE, PENDING_MAX_AGE_HOURS, API_DELAY_SECONDS
from telegram_bot import (
    get_updates, answer_callback_query, edit_message_reply_markup,
    send_message, send_photo, ADMIN_CHAT_ID
)
from publisher import create_article_file, create_telegram_message

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "miakutikov/konopla")


def load_json(filepath, default):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Bot commands
# ---------------------------------------------------------------------------

def trigger_pipeline():
    """Тригерить pipeline workflow через GitHub API."""
    if not GITHUB_TOKEN:
        print("[WARN] GITHUB_TOKEN not set, cannot trigger pipeline")
        return False

    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/pipeline.yml/dispatches"
    payload = json.dumps({"ref": "main"}).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            # 204 No Content = success
            print(f"[OK] Pipeline triggered, status={resp.status}")
            return True
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")[:200]
        except Exception:
            pass
        print(f"[ERROR] Failed to trigger pipeline: {e.code} {body}")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to trigger pipeline: {e}")
        return False


def handle_command(text, pending_articles):
    """Обробляє команду від адміна. Повертає текст відповіді."""
    cmd = text.strip().lower().split()[0] if text.strip() else ""

    if cmd == "/run":
        ok = trigger_pipeline()
        if ok:
            return "🚀 Pipeline запущено! Нові новини з'являться через кілька хвилин."
        return "❌ Не вдалось запустити pipeline. Перевір GitHub Token."

    elif cmd == "/status":
        count = len(pending_articles)
        if count == 0:
            return "📋 Немає статей на модерації."

        lines = [f"📋 <b>На модерації: {count} статей</b>\n"]
        for i, a in enumerate(pending_articles[:10], 1):
            title = a.get("rewritten", {}).get("title", "?")[:50]
            created = a.get("created_at", "")[:16].replace("T", " ")
            lines.append(f"{i}. {title}\n   <i>{created}</i>")
        if count > 10:
            lines.append(f"\n... та ще {count - 10}")
        return "\n".join(lines)

    elif cmd == "/help" or cmd == "/start":
        return (
            "🌿 <b>KONOPLA.UA Bot</b>\n\n"
            "Доступні команди:\n\n"
            "/run — запустити збір новин\n"
            "/status — статус модерації\n"
            "/help — ця довідка\n\n"
            "Для модерації — використовуй кнопки ✅/❌ під статтями."
        )

    return None  # Unknown command — ignore


# ---------------------------------------------------------------------------
# Main moderator logic
# ---------------------------------------------------------------------------

def run_moderator():
    print("=" * 60)
    print("🔍 KONOPLA.UA — Moderator")
    print("=" * 60)

    # Load pending articles
    pending = load_json(PENDING_FILE, {"articles": []})
    pending_map = {a["id"]: a for a in pending["articles"] if a.get("status") == "pending"}
    print(f"[INFO] {len(pending_map)} pending articles")

    # Load Telegram offset
    offset_data = load_json(TELEGRAM_OFFSET_FILE, {"offset": 0})
    offset = offset_data.get("offset", 0)

    # Poll Telegram for updates (callback_query + message)
    updates = get_updates(offset=offset)
    print(f"[INFO] Got {len(updates)} Telegram updates")

    approved_ids = []
    rejected_ids = []

    for update in updates:
        update_id = update.get("update_id", 0)
        offset = max(offset, update_id + 1)

        # --- Handle callback_query (moderation buttons) ---
        callback = update.get("callback_query")
        if callback:
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

            continue

        # --- Handle message (bot commands) ---
        msg = update.get("message")
        if not msg:
            continue

        chat_id = str(msg.get("chat", {}).get("id", ""))
        text = msg.get("text", "")

        # Only accept commands from admin
        if chat_id != str(ADMIN_CHAT_ID):
            continue

        if not text.startswith("/"):
            continue

        print(f"[CMD] {text}")
        reply = handle_command(text, pending["articles"])
        if reply:
            send_message(reply, chat_id=ADMIN_CHAT_ID)

    # Save updated offset
    save_json(TELEGRAM_OFFSET_FILE, {"offset": offset})

    # Early exit if no pending articles
    if not pending["articles"]:
        print("[INFO] No pending articles. Done.")
        save_result(0)
        return 0

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
