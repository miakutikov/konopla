"""
rewriter.py — Переписує новини українською.
Primary: Gemini API (безкоштовний). Fallback: OpenRouter (безкоштовні моделі).
"""

import json
import os
import re
import time
import urllib.request
import urllib.error
from config import GEMINI_SYSTEM_PROMPT


# === Gemini API ===
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# === OpenRouter API (fallback) ===
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS = [
    "google/gemma-3n-e4b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "z-ai/glm-4.5-air:free",
]


def rewrite_article(title, summary, source_url, content="", source_images=None):
    """
    Рерайтить статтю українською. Спочатку Gemini, потім OpenRouter.
    Повертає dict або None.
    """
    # Use full content if available, otherwise summary
    article_body = content if content and len(content) > len(summary) else summary

    user_prompt = f"""Перепиши цю новину:

Заголовок: {title}

Повний текст: {article_body}

Джерело: {source_url}"""

    # Try Gemini first
    gemini_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)
    if gemini_key:
        result = _try_gemini(gemini_key, user_prompt)
        if result:
            return result

    # Fallback to OpenRouter
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", OPENROUTER_API_KEY)
    if openrouter_key:
        for model in OPENROUTER_MODELS:
            result = _try_openrouter(openrouter_key, model, user_prompt)
            if result is not None:
                return result

    print("[ERROR] All rewrite methods failed")
    return None


def _api_request_with_retry(url, payload, headers, label, max_attempts=2):
    """Загальний HTTP POST з retry. Повертає розпарсений JSON або None."""
    data = json.dumps(payload).encode("utf-8")

    for attempt in range(max_attempts):
        try:
            req = urllib.request.Request(
                url, data=data, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))

        except urllib.error.HTTPError as e:
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                error_body = ""
            print(f"   [WARN] {label} error (attempt {attempt+1}): {e.code} {error_body[:150]}")
            if e.code == 429:
                time.sleep(5)
                continue
            else:
                return None

        except Exception as e:
            print(f"   [WARN] {label} request failed (attempt {attempt+1}): {e}")
            if attempt < max_attempts - 1:
                time.sleep(3)

    return None


def _try_gemini(api_key, user_prompt):
    """Пробує Gemini API напряму."""
    print("   🤖 Trying: Gemini 2.5 Flash")

    url = f"{GEMINI_API_URL}?key={api_key}"
    payload = {
        "contents": [{
            "parts": [{"text": GEMINI_SYSTEM_PROMPT + "\n\n" + user_prompt}]
        }],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 8192
        }
    }

    result = _api_request_with_retry(
        url, payload, {"Content-Type": "application/json"}, "Gemini"
    )
    if not result:
        return None

    try:
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        return _parse_json_response(text)
    except (KeyError, IndexError) as e:
        print(f"   [WARN] Gemini response parse error: {e}")
        return None


def _try_openrouter(api_key, model, user_prompt):
    """Пробує одну модель через OpenRouter."""
    print(f"   🤖 Model: {model}")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": GEMINI_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.4,
        "max_tokens": 8192,
    }

    result = _api_request_with_retry(
        OPENROUTER_URL, payload,
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://konopla.ua",
            "X-Title": "KONOPLA.UA"
        },
        model
    )
    if not result:
        return None

    try:
        text = result["choices"][0]["message"]["content"]
        return _parse_json_response(text)
    except (KeyError, IndexError) as e:
        print(f"   [WARN] {model} response parse error: {e}")
        return None


def _parse_json_response(text):
    """Парсить JSON-відповідь від моделі."""
    text = re.sub(r"^```json\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())

    try:
        article_data = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"   [WARN] JSON parse error: {e}")
        return None

    # Check if AI rejected the article as irrelevant
    if article_data.get("rejected"):
        reason = article_data.get("reason", "невідома причина")
        print(f"   🚫 AI rejected: {reason}")
        return {"rejected": True, "reason": reason}

    required = ["title", "summary", "content", "category", "tags"]
    if not all(key in article_data for key in required):
        print(f"   [WARN] Missing fields: {list(article_data.keys())}")
        return None

    allowed_categories = {
        "бізнес", "агро", "текстиль", "будівництво", "харчова",
        "екологія", "законодавство", "відео", "наука", "косметика",
        "біопластик", "автопром", "енергетика", "інше"
    }
    if article_data.get("category", "інше") not in allowed_categories:
        print(f"   [WARN] Invalid category '{article_data['category']}', defaulting to 'інше'")
        article_data["category"] = "інше"

    print("   ✅ OK")
    return article_data


if __name__ == "__main__":
    result = rewrite_article(
        "Hemp concrete blocks now available for European construction market",
        "A new factory in Germany has started mass production of hempcrete blocks.",
        "https://example.com/test"
    )
    if result:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Rewrite failed")
