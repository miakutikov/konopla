"""
monitor.py — Моніторинг та алерти

Відправляє повідомлення в Telegram якщо:
- Pipeline впав повністю
- Занадто багато помилок за один запуск
- Gemini API повертає помилки
- RSS фіди недоступні
"""

import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone


TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Separate admin chat ID for alerts (falls back to channel if not set)
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "")


def _get_alert_chat_id():
    """Повертає chat ID для алертів (адмін або канал)."""
    return ADMIN_CHAT_ID or TELEGRAM_CHAT_ID


def send_alert(message, level="WARN"):
    """
    Відправляє алерт в Telegram.
    level: INFO, WARN, ERROR, CRITICAL
    """
    chat_id = _get_alert_chat_id()
    token = os.environ.get("TELEGRAM_TOKEN", TELEGRAM_TOKEN)
    
    if not token or not chat_id:
        print(f"[{level}] Alert (no Telegram): {message}")
        return False
    
    emoji = {
        "INFO": "ℹ️",
        "WARN": "⚠️",
        "ERROR": "❌",
        "CRITICAL": "🚨",
    }.get(level, "📋")
    
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    text = (
        f"{emoji} <b>Konopla.UA — {level}</b>\n\n"
        f"{message}\n\n"
        f"<i>⏰ {now}</i>"
    )
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_notification": level in ("INFO", "WARN"),
    }
    
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return result.get("ok", False)
    except Exception as e:
        print(f"[ERROR] Failed to send alert: {e}")
        return False


def send_pipeline_report(published, failed, total, duration_sec, skipped=0):
    """Відправляє звіт про роботу pipeline.

    published - успішно оброблено і збережено як draft
    failed    - справжні помилки (API недоступний, JSON parse error тощо)
    total     - знайдено в RSS
    skipped   - AI відхилив як нерелевантне (нормальна поведінка, не помилка)
    """
    if published == 0 and total == 0:
        # No news found — not an error, just log (don't spam Telegram)
        print("[INFO] Запуск завершено. Нових новин не знайдено.")
        return

    skipped_line = f"🚫 Нерелевантних: {skipped}\n" if skipped > 0 else ""

    if failed > 0 and published == 0:
        # All found articles failed with real errors — serious problem
        send_alert(
            f"Pipeline завершився з помилками!\n"
            f"📰 Знайдено: {total}\n"
            f"❌ Помилок API: {failed}\n"
            f"{skipped_line}"
            f"✅ Опубліковано: 0\n"
            f"⏱ Час: {duration_sec:.0f}с",
            level="ERROR"
        )
    elif failed > 2:
        # More than 2 real API errors — worth knowing about
        send_alert(
            f"Помилки API у pipeline:\n"
            f"📰 Знайдено: {total}\n"
            f"❌ Помилок API: {failed}\n"
            f"{skipped_line}"
            f"✅ Опубліковано: {published}\n"
            f"⏱ Час: {duration_sec:.0f}с",
            level="WARN"
        )
    # Skipped (irrelevant) articles are normal — no alert needed


def send_crash_alert(error_message):
    """Відправляє алерт про критичну помилку pipeline."""
    send_alert(
        f"Pipeline впав з помилкою:\n\n<code>{error_message[:500]}</code>",
        level="CRITICAL"
    )


if __name__ == "__main__":
    send_alert("Тестовий алерт — моніторинг працює!", level="INFO")
