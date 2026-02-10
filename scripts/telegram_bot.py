"""
telegram_bot.py — Публікує анонси в Telegram-канал
Підтримує текстові повідомлення та повідомлення з фото.
"""

import json
import os
import urllib.request
import urllib.error
import time


TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def send_message(text, parse_mode="HTML"):
    """
    Відправляє текстове повідомлення в Telegram-канал.
    Повертає True якщо успішно, False якщо помилка.
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[WARN] Telegram credentials not set, skipping")
        return False
    
    token = os.environ.get("TELEGRAM_TOKEN", TELEGRAM_TOKEN)
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False,
    }
    
    return _send_request(url, payload)


def send_photo(photo_url, caption, parse_mode="HTML"):
    """
    Відправляє фото з підписом в Telegram-канал.
    Повертає True якщо успішно, False якщо помилка.
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[WARN] Telegram credentials not set, skipping")
        return False
    
    token = os.environ.get("TELEGRAM_TOKEN", TELEGRAM_TOKEN)
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID)
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    
    # Telegram caption limit is 1024 chars
    if len(caption) > 1024:
        caption = caption[:1020] + "..."
    
    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": parse_mode,
    }
    
    success = _send_request(url, payload)
    
    # If photo sending fails (e.g. bad URL), fallback to text message
    if not success:
        print("[INFO] Photo send failed, falling back to text message")
        return send_message(caption)
    
    return success


def _send_request(url, payload):
    """Внутрішня функція — відправляє запит до Telegram API з retry."""
    data = json.dumps(payload).encode("utf-8")
    
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            
            if result.get("ok"):
                print("[OK] Telegram message sent")
                return True
            else:
                print(f"[WARN] Telegram API error: {result}")
                return False
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.readable() else ""
            print(f"[WARN] Telegram error (attempt {attempt+1}): {e.code} {error_body[:200]}")
            if e.code == 429:  # Rate limited
                retry_after = 10
                try:
                    retry_after = json.loads(error_body).get("parameters", {}).get("retry_after", 10)
                except Exception:
                    pass
                time.sleep(retry_after)
            else:
                time.sleep(3)
                
        except Exception as e:
            print(f"[WARN] Telegram request failed (attempt {attempt+1}): {e}")
            time.sleep(3)
    
    return False


if __name__ == "__main__":
    test_msg = "🌿 <b>Тест</b>\n\nЦе тестове повідомлення від бота Konopla.UA"
    send_message(test_msg)
