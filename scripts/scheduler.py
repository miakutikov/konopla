#!/usr/bin/env python3
"""
scheduler.py — Перевіряє заплановані дії та виконує їх коли час настав.

Запускається через cron (кожні 30 хв). Читає data/scheduled.json,
порівнює scheduled_at з поточним часом UTC, та:
- deploy → triggers moderate.yml
- telegram → пише telegram_queue.json + triggers telegram_post.yml
- threads → пише threads_queue.json + triggers threads_post.yml
"""

import json
import os
import sys
import requests
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEDULED_FILE = os.path.join(PROJECT_ROOT, "data", "scheduled.json")
TELEGRAM_QUEUE_FILE = os.path.join(PROJECT_ROOT, "data", "telegram_queue.json")
THREADS_QUEUE_FILE = os.path.join(PROJECT_ROOT, "data", "threads_queue.json")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "miakutikov/konopla")


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


def trigger_workflow(workflow_filename):
    """Triggers a GitHub Actions workflow via workflow_dispatch."""
    if not GITHUB_TOKEN:
        print(f"[WARN] No GITHUB_TOKEN, cannot trigger {workflow_filename}")
        return False

    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{workflow_filename}/dispatches"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {"ref": "main"}

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code == 204:
            print(f"[OK] Triggered {workflow_filename}")
            return True
        else:
            print(f"[ERROR] Failed to trigger {workflow_filename}: {resp.status_code} {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"[ERROR] Exception triggering {workflow_filename}: {e}")
        return False


def process_deploy(items, now):
    """Обробляє заплановані деплої."""
    due = []
    remaining = []

    for item in items:
        scheduled_at = datetime.fromisoformat(item["scheduled_at"]).replace(tzinfo=timezone.utc)
        if scheduled_at <= now:
            due.append(item)
        else:
            remaining.append(item)

    if due:
        print(f"[DEPLOY] {len(due)} scheduled deploy(s) due")
        trigger_workflow("moderate.yml")

    return remaining


def process_telegram(items, now):
    """Обробляє заплановані Telegram постинги."""
    due = []
    remaining = []

    for item in items:
        scheduled_at = datetime.fromisoformat(item["scheduled_at"]).replace(tzinfo=timezone.utc)
        if scheduled_at <= now:
            due.append(item)
        else:
            remaining.append(item)

    if due:
        print(f"[TELEGRAM] {len(due)} scheduled Telegram post(s) due")

        # Collect all articles from due items
        all_articles = []
        for item in due:
            for article in item.get("articles", []):
                all_articles.append(article)

        if all_articles:
            # Write telegram_queue.json
            queue = load_queue_file(TELEGRAM_QUEUE_FILE)
            queue["articles"].extend(all_articles)
            save_queue_file(TELEGRAM_QUEUE_FILE, queue)
            print(f"[TELEGRAM] Wrote {len(all_articles)} articles to telegram_queue.json")

            trigger_workflow("telegram_post.yml")

    return remaining


def process_threads(items, now):
    """Обробляє заплановані Threads постинги."""
    due = []
    remaining = []

    for item in items:
        scheduled_at = datetime.fromisoformat(item["scheduled_at"]).replace(tzinfo=timezone.utc)
        if scheduled_at <= now:
            due.append(item)
        else:
            remaining.append(item)

    if due:
        print(f"[THREADS] {len(due)} scheduled Threads post(s) due")

        # Collect all articles from due items
        all_articles = []
        for item in due:
            for article in item.get("articles", []):
                all_articles.append(article)

        if all_articles:
            # Write threads_queue.json
            queue = load_queue_file(THREADS_QUEUE_FILE)
            queue["articles"].extend(all_articles)
            save_queue_file(THREADS_QUEUE_FILE, queue)
            print(f"[THREADS] Wrote {len(all_articles)} articles to threads_queue.json")

            trigger_workflow("threads_post.yml")

    return remaining


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
        return 0

    # Process each queue
    scheduled["deploy"] = process_deploy(deploy_items, now)
    scheduled["telegram"] = process_telegram(telegram_items, now)
    scheduled["threads"] = process_threads(threads_items, now)

    # Save updated scheduled.json
    save_scheduled(scheduled)

    remaining = len(scheduled["deploy"]) + len(scheduled["telegram"]) + len(scheduled["threads"])
    executed = total_scheduled - remaining
    print(f"\n[INFO] Executed: {executed}, Remaining: {remaining}")

    return 0


if __name__ == "__main__":
    exit_code = run_scheduler()
    sys.exit(exit_code)
