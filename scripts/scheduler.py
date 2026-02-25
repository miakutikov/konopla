#!/usr/bin/env python3
"""
scheduler.py — Перевіряє заплановані дії та виконує їх коли час настав.

Запускається через cron (кожні 30 хв). Читає data/scheduled.json,
порівнює scheduled_at з поточним часом UTC, та:
- deploy → triggers moderate.yml (через trigger file)
- telegram → пише telegram_queue.json + triggers telegram_post.yml
- threads → пише threads_queue.json + triggers threads_post.yml

ВАЖЛИВО: scheduler.py НЕ тригерить workflows напряму!
Натомість записує список workflows у data/trigger_workflows.json.
Workflow scheduler.yml тригерить їх ПІСЛЯ git commit+push,
щоб уникнути race condition.
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEDULED_FILE = os.path.join(PROJECT_ROOT, "data", "scheduled.json")
TELEGRAM_QUEUE_FILE = os.path.join(PROJECT_ROOT, "data", "telegram_queue.json")
THREADS_QUEUE_FILE = os.path.join(PROJECT_ROOT, "data", "threads_queue.json")
TRIGGER_FILE = os.path.join(PROJECT_ROOT, "data", "trigger_workflows.json")


def load_scheduled():
    """Завантажує scheduled.json."""
    if os.path.exists(SCHEDULED_FILE):
        with open(SCHEDULED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"deploy": [], "telegram": [], "threads": []}


def save_scheduled(data):
    """Зберігає scheduled.json."""
    os.makedirs(os.path.dirname(SCHEDULED_FILE), exist_ok=True)
    with open(SCHEDULED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_queue_file(filepath):
    """Завантажує queue JSON файл."""
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"articles": []}


def save_queue_file(filepath, data):
    """Зберігає queue JSON файл."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_trigger_list(workflows):
    """Зберігає список workflows для тригера у trigger_workflows.json."""
    os.makedirs(os.path.dirname(TRIGGER_FILE), exist_ok=True)
    with open(TRIGGER_FILE, "w", encoding="utf-8") as f:
        json.dump({"workflows": workflows}, f, ensure_ascii=False, indent=2)


def process_deploy(items, now):
    """Обробляє заплановані деплої. Повертає (remaining, triggered_workflows)."""
    due = []
    remaining = []

    for item in items:
        scheduled_at = datetime.fromisoformat(item["scheduled_at"]).replace(tzinfo=timezone.utc)
        if scheduled_at <= now:
            due.append(item)
        else:
            remaining.append(item)

    triggered = []
    if due:
        print(f"[DEPLOY] {len(due)} scheduled deploy(s) due")
        triggered.append("moderate.yml")

    return remaining, triggered


def process_telegram(items, now):
    """Обробляє заплановані Telegram постинги. Повертає (remaining, triggered_workflows)."""
    due = []
    remaining = []

    for item in items:
        scheduled_at = datetime.fromisoformat(item["scheduled_at"]).replace(tzinfo=timezone.utc)
        if scheduled_at <= now:
            due.append(item)
        else:
            remaining.append(item)

    triggered = []
    if due:
        print(f"[TELEGRAM] {len(due)} scheduled Telegram post(s) due")

        # Collect all articles from due items
        all_articles = []
        for item in due:
            for article in item.get("articles", []):
                all_articles.append(article)
            # Also support per-article format (item itself is the article)
            if "filename" in item and "articles" not in item:
                all_articles.append({
                    "filename": item["filename"],
                    "title": item.get("title", ""),
                    "category": item.get("category", ""),
                })

        if all_articles:
            # Write telegram_queue.json
            queue = load_queue_file(TELEGRAM_QUEUE_FILE)
            queue["articles"].extend(all_articles)
            save_queue_file(TELEGRAM_QUEUE_FILE, queue)
            print(f"[TELEGRAM] Wrote {len(all_articles)} articles to telegram_queue.json")

            triggered.append("telegram_post.yml")

    return remaining, triggered


def process_threads(items, now):
    """Обробляє заплановані Threads постинги. Повертає (remaining, triggered_workflows)."""
    due = []
    remaining = []

    for item in items:
        scheduled_at = datetime.fromisoformat(item["scheduled_at"]).replace(tzinfo=timezone.utc)
        if scheduled_at <= now:
            due.append(item)
        else:
            remaining.append(item)

    triggered = []
    if due:
        print(f"[THREADS] {len(due)} scheduled Threads post(s) due")

        # Collect all articles from due items
        all_articles = []
        for item in due:
            for article in item.get("articles", []):
                all_articles.append(article)
            # Also support per-article format
            if "filename" in item and "articles" not in item:
                all_articles.append({
                    "filename": item["filename"],
                    "title": item.get("title", ""),
                    "category": item.get("category", ""),
                })

        if all_articles:
            # Write threads_queue.json
            queue = load_queue_file(THREADS_QUEUE_FILE)
            queue["articles"].extend(all_articles)
            save_queue_file(THREADS_QUEUE_FILE, queue)
            print(f"[THREADS] Wrote {len(all_articles)} articles to threads_queue.json")

            triggered.append("threads_post.yml")

    return remaining, triggered


def run_scheduler():
    """Основна функція планувальника."""
    print("=" * 60)
    print("⏰ KONOPLA.UA — Scheduler")
    print("=" * 60)

    now = datetime.now(timezone.utc)
    print(f"[INFO] Current UTC time: {now.isoformat()}")

    scheduled = load_scheduled()

    deploy_items = scheduled.get("deploy", [])
    telegram_items = scheduled.get("telegram", [])
    threads_items = scheduled.get("threads", [])

    total_scheduled = len(deploy_items) + len(telegram_items) + len(threads_items)
    print(f"[INFO] Scheduled items: deploy={len(deploy_items)}, telegram={len(telegram_items)}, threads={len(threads_items)}")

    if total_scheduled == 0:
        print("[INFO] No scheduled items. Done.")
        # Clean up any stale trigger file
        save_trigger_list([])
        return 0

    # Process each queue — collect workflows to trigger
    all_triggered = []

    scheduled["deploy"], deploy_triggered = process_deploy(deploy_items, now)
    all_triggered.extend(deploy_triggered)

    scheduled["telegram"], telegram_triggered = process_telegram(telegram_items, now)
    all_triggered.extend(telegram_triggered)

    scheduled["threads"], threads_triggered = process_threads(threads_items, now)
    all_triggered.extend(threads_triggered)

    # Save updated scheduled.json FIRST (before any triggers)
    save_scheduled(scheduled)

    # Save trigger list for scheduler.yml to process AFTER commit+push
    # Deduplicate workflows
    unique_workflows = list(dict.fromkeys(all_triggered))
    save_trigger_list(unique_workflows)

    remaining = len(scheduled["deploy"]) + len(scheduled["telegram"]) + len(scheduled["threads"])
    executed = total_scheduled - remaining
    print(f"\n[INFO] Executed: {executed}, Remaining: {remaining}")
    if unique_workflows:
        print(f"[INFO] Workflows to trigger: {', '.join(unique_workflows)}")

    return 0


if __name__ == "__main__":
    exit_code = run_scheduler()
    sys.exit(exit_code)
