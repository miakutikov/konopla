"""
telegram_bot.py — Telegram: публікація в канал + модерація через адмін-чат
"""

import json
import os
import urllib.request
import urllib.error
import time


TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "")


def send_message(text, chat_id=None, parse_mode="HTML"):
    """Відправляє текстове повідомлення. За замовчуванням — в канал."""
    if not TELEGRAM_TOKEN:
        print("[WARN] TELEGRAM_TOKEN not set, skipping")
        return False

    chat = chat_id or TELEGRAM_CHAT_ID
    if not chat:
        print("[WARN] Chat ID not set, skipping")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    # Telegram limit: 4096 chars per message
    if len(text) > 4096:
        text = text[:4092] + "..."

    payload = {
        "chat_id": chat,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False,
    }
    return _send_request(url, payload)


def send_photo(photo_url=None, caption="", chat_id=None, parse_mode="HTML", photo_path=None):
    """
    Відправляє фото з підписом. За замовчуванням — в канал.
    photo_url: URL зображення (для Unsplash)
    photo_path: локальний шлях до файлу (для Gemini-генерованих)
    """
    if not TELEGRAM_TOKEN:
        print("[WARN] TELEGRAM_TOKEN not set, skipping")
        return False

    chat = chat_id or TELEGRAM_CHAT_ID
    if not chat:
        print("[WARN] Chat ID not set, skipping")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"

    if len(caption) > 1024:
        caption = caption[:1020] + "..."

    # If local file — send via multipart/form-data
    if photo_path and os.path.exists(photo_path):
        success = _send_photo_file(url, chat, photo_path, caption, parse_mode)
        if success:
            return True
        print("[INFO] Photo file send failed, trying URL fallback")

    # URL-based send (Unsplash or fallback)
    if photo_url:
        payload = {
            "chat_id": chat,
            "photo": photo_url,
            "caption": caption,
            "parse_mode": parse_mode,
        }
        success = _send_request(url, payload)
        if success:
            return True

    print("[INFO] Photo send failed, falling back to text message")
    return send_message(caption, chat_id=chat)


def _send_photo_file(url, chat_id, photo_path, caption, parse_mode="HTML"):
    """Відправляє локальний файл зображення через multipart/form-data."""
    import mimetypes

    boundary = "----KonoplaUploadBoundary"
    mime_type = mimetypes.guess_type(photo_path)[0] or "image/png"
    filename = os.path.basename(photo_path)

    with open(photo_path, "rb") as f:
        file_data = f.read()

    # Build multipart body
    body = b""
    # chat_id field
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'.encode()
    # caption field
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'.encode()
    # parse_mode field
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="parse_mode"\r\n\r\n{parse_mode}\r\n'.encode()
    # photo file
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="photo"; filename="{filename}"\r\n'.encode()
    body += f"Content-Type: {mime_type}\r\n\r\n".encode()
    body += file_data
    body += f"\r\n--{boundary}--\r\n".encode()

    try:
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return result.get("ok", False)
    except Exception as e:
        print(f"[WARN] Photo file upload failed: {e}")
        return False


def send_for_moderation(article_data, article_id):
    """
    Надсилає прев'ю статті адміну з кнопками Опублікувати/Відхилити.
    Повертає message_id або None.
    """
    if not TELEGRAM_TOKEN or not ADMIN_CHAT_ID:
        print("[WARN] TELEGRAM_TOKEN or ADMIN_CHAT_ID not set")
        return None

    category = article_data.get("category", "інше")
    title = article_data.get("title", "Без заголовку")
    summary = article_data.get("summary", "")

    text = (
        f"📰 <b>Нова стаття для модерації</b>\n\n"
        f"<b>{title}</b>\n\n"
        f"{summary}\n\n"
        f"Категорія: {category}\n"
        f"ID: <code>{article_id}</code>"
    )

    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Опублікувати", "callback_data": f"approve_{article_id}"},
            {"text": "❌ Відхилити", "callback_data": f"reject_{article_id}"}
        ]]
    }

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": ADMIN_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": keyboard,
    }

    result = _send_request_raw(url, payload)
    if result and result.get("ok"):
        msg_id = result["result"]["message_id"]
        print(f"[OK] Sent for moderation, message_id={msg_id}")
        return msg_id
    return None


def get_updates(offset=0):
    """Опитує Telegram API для callback_query та message оновлень."""
    if not TELEGRAM_TOKEN:
        return []

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    payload = {
        "offset": offset,
        "timeout": 5,
        "allowed_updates": ["callback_query", "message"],
    }

    result = _send_request_raw(url, payload)
    if result and result.get("ok"):
        return result.get("result", [])
    return []


def answer_callback_query(callback_query_id, text=""):
    """Підтверджує натискання inline-кнопки."""
    if not TELEGRAM_TOKEN:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
    payload = {
        "callback_query_id": callback_query_id,
        "text": text,
    }
    return _send_request(url, payload)


def edit_message_reply_markup(chat_id, message_id):
    """Видаляє inline-кнопки після рішення адміна."""
    if not TELEGRAM_TOKEN:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageReplyMarkup"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "reply_markup": {"inline_keyboard": []},
    }
    return _send_request(url, payload)


def edit_message_text(chat_id, message_id, new_text, parse_mode="HTML"):
    """Редагує текст повідомлення (без кнопок)."""
    if not TELEGRAM_TOKEN:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": new_text,
        "parse_mode": parse_mode,
    }
    return _send_request(url, payload)


def _send_request_raw(url, payload):
    """Відправляє запит і повертає повну відповідь JSON."""
    data = json.dumps(payload).encode("utf-8")

    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.readable() else ""
            print(f"[WARN] Telegram error (attempt {attempt+1}): {e.code} {error_body[:200]}")
            if e.code == 429:
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

    return None


def _send_request(url, payload):
    """Відправляє запит і повертає True/False."""
    result = _send_request_raw(url, payload)
    if result and result.get("ok"):
        print("[OK] Telegram message sent")
        return True
    return False


if __name__ == "__main__":
    test_msg = "🌿 <b>Тест</b>\n\nЦе тестове повідомлення від KONOPLA.UA"
    send_message(test_msg)
