#!/usr/bin/env python3
"""
moderator.py — Telegram bot commands + deploy pipeline.

Модерація тепер відбувається через адмін-панель на сайті (konopla.ua/admin/).
Цей скрипт обробляє тільки Telegram-команди бота та деплоїть сайт.

Команди:
  /run      — запустити pipeline (збір новин)
  /status   — статус draft-статей
  /catalog  — список компаній у каталозі
  /add      — додати компанію
  /del      — видалити компанію
  /help     — список команд
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import TELEGRAM_OFFSET_FILE
from telegram_bot import get_updates, send_message, ADMIN_CHAT_ID
from utils import load_json, save_json

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "miakutikov/konopla")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_FILE = os.path.join(PROJECT_ROOT, "data", "catalog.json")
DRAFTS_FILE = os.path.join(PROJECT_ROOT, "data", "drafts.json")


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


def handle_command(text):
    """Обробляє команду від адміна. Повертає текст відповіді."""
    cmd = text.strip().lower().split()[0] if text.strip() else ""

    if cmd == "/run":
        ok = trigger_pipeline()
        if ok:
            return "🚀 Pipeline запущено! Нові новини з'являться через кілька хвилин."
        return "❌ Не вдалось запустити pipeline. Перевір GitHub Token."

    elif cmd == "/status":
        drafts = load_json(DRAFTS_FILE, {"articles": []})
        count = len(drafts["articles"])
        if count == 0:
            return "📋 Немає статей на модерації.\n\n👉 <a href=\"https://konopla.ua/admin/\">Адмін-панель</a>"

        lines = [f"📋 <b>На модерації: {count} статей</b>\n"]
        for i, a in enumerate(drafts["articles"][:10], 1):
            title = a.get("title", "?")[:50]
            created = a.get("created_at", "")[:16].replace("T", " ")
            lines.append(f"{i}. {title}\n   <i>{created}</i>")
        if count > 10:
            lines.append(f"\n... та ще {count - 10}")
        lines.append(f"\n👉 <a href=\"https://konopla.ua/admin/\">Модерувати</a>")
        return "\n".join(lines)

    elif cmd == "/catalog":
        catalog = load_json(CATALOG_FILE, {"categories": [], "companies": []})
        active = [c for c in catalog["companies"] if c.get("status") == "active"]
        if not active:
            return "📂 Каталог порожній."

        cat_map = {c["id"]: c["name"] for c in catalog["categories"]}
        groups = {}
        for comp in active:
            cat_name = cat_map.get(comp["category_id"], "Інше")
            groups.setdefault(cat_name, []).append(comp["name"])

        lines = [f"📂 <b>Каталог: {len(active)} компаній</b>\n"]
        for cat_name, names in groups.items():
            lines.append(f"\n<b>{cat_name}</b> ({len(names)}):")
            for name in names[:5]:
                lines.append(f"  • {name}")
            if len(names) > 5:
                lines.append(f"  ... та ще {len(names) - 5}")
        return "\n".join(lines)

    elif text.startswith("/add "):
        parts_str = text[5:].strip()
        parts = [p.strip() for p in parts_str.split("|")]
        if len(parts) < 4:
            cat_ids = "vyroshuvannya, tekstyl, budivnytstvo, kharchova, kosmetyka, nasinnevi, naukovi, torgivlia, hromadski"
            return (
                "❌ Формат:\n"
                "<code>/add Назва | category_id | Опис | Місто | Сайт | Тел | Email</code>\n\n"
                f"Категорії:\n<code>{cat_ids}</code>\n\n"
                "Сайт, тел, email — необов'язкові (можна пропустити)"
            )

        name = parts[0]
        category_id = parts[1].lower().strip()
        description = parts[2]
        location = parts[3]
        website = parts[4].strip() if len(parts) > 4 and parts[4].strip() not in ("", "-") else ""
        phone = parts[5].strip() if len(parts) > 5 and parts[5].strip() not in ("", "-") else ""
        email = parts[6].strip() if len(parts) > 6 and parts[6].strip() not in ("", "-") else ""

        catalog = load_json(CATALOG_FILE, {"categories": [], "companies": []})
        valid_cat_ids = {c["id"] for c in catalog["categories"]}
        if category_id not in valid_cat_ids:
            return f"❌ Невідома категорія: {category_id}\n\nДоступні: {', '.join(sorted(valid_cat_ids))}"

        existing_names = {c["name"].lower() for c in catalog["companies"]}
        if name.lower() in existing_names:
            return f"❌ Компанія «{name}» вже існує в каталозі."

        max_num = 0
        for c in catalog["companies"]:
            if c["id"].startswith("hemp-ua-"):
                try:
                    max_num = max(max_num, int(c["id"].replace("hemp-ua-", "")))
                except ValueError:
                    pass
        new_id = f"hemp-ua-{max_num + 1:03d}"

        catalog["companies"].append({
            "id": new_id,
            "name": name,
            "category_id": category_id,
            "description": description,
            "location": location,
            "website": website,
            "phone": phone,
            "email": email,
            "status": "active",
            "added_at": datetime.now(timezone.utc).isoformat(),
        })
        save_json(CATALOG_FILE, catalog)
        return f"✅ Додано: <b>{name}</b>\nКатегорія: {category_id}\nID: {new_id}"

    elif text.startswith("/del "):
        name_to_del = text[5:].strip()
        if not name_to_del:
            return "❌ Формат: /del Назва компанії"

        catalog = load_json(CATALOG_FILE, {"categories": [], "companies": []})
        found = False
        for comp in catalog["companies"]:
            if comp["name"].lower() == name_to_del.lower() and comp.get("status") == "active":
                comp["status"] = "inactive"
                found = True
                break

        if not found:
            return f"❌ Компанію «{name_to_del}» не знайдено серед активних."

        save_json(CATALOG_FILE, catalog)
        return f"🗑️ Видалено: <b>{name_to_del}</b>"

    elif cmd == "/help" or cmd == "/start":
        return (
            "🌿 <b>KONOPLA.UA Bot</b>\n\n"
            "Доступні команди:\n\n"
            "📰 <b>Новини:</b>\n"
            "/run — запустити збір новин\n"
            "/status — статус модерації\n\n"
            "📂 <b>Каталог:</b>\n"
            "/catalog — список компаній\n"
            "/add — додати компанію\n"
            "/del — видалити компанію\n\n"
            "🔧 <b>Модерація:</b>\n"
            "Через адмін-панель на сайті:\n"
            "👉 https://konopla.ua/admin/\n\n"
            "/help — ця довідка"
        )

    return None  # Unknown command — ignore


# ---------------------------------------------------------------------------
# Main moderator logic
# ---------------------------------------------------------------------------

def run_moderator():
    print("=" * 60)
    print("🔍 KONOPLA.UA — Moderator (commands only)")
    print("=" * 60)

    # Load Telegram offset
    offset_data = load_json(TELEGRAM_OFFSET_FILE, {"offset": 0})
    offset = offset_data.get("offset", 0)

    # Poll Telegram for updates (bot commands only)
    updates = get_updates(offset=offset)
    print(f"[INFO] Got {len(updates)} Telegram updates")

    for update in updates:
        update_id = update.get("update_id", 0)
        offset = max(offset, update_id + 1)

        # Handle message (bot commands)
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
        reply = handle_command(text)
        if reply:
            send_message(reply, chat_id=ADMIN_CHAT_ID)

    # Save updated offset
    save_json(TELEGRAM_OFFSET_FILE, {"offset": offset})

    print("[INFO] Moderator done.")
    return 0


if __name__ == "__main__":
    sys.exit(run_moderator())
