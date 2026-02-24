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

    # Append source images for contextual placement
    if source_images:
        images_text = "\n".join(
            f"- {img['url']}" + (f" ({img['alt']})" if img.get('alt') else "")
            for img in source_images[:5]
        )
        user_prompt += f"""

Оригінальні зображення з джерела (вбудуй 1-3 найкращих у текст статті між абзацами, формат: ![короткий опис](URL)):
{images_text}"""

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


def _try_gemini(api_key, user_prompt):
    """Пробує Gemini API напряму."""
    print("   🤖 Trying: Gemini 2.5 Flash")

    url = f"{GEMINI_API_URL}?key={api_key}"
    payload = {
        "contents": [{
            "parts": [{"text": GEMINI_SYSTEM_PROMPT + "\n\n" + user_prompt}]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 8192
        }
    }

    data = json.dumps(payload).encode("utf-8")

    for attempt in range(2):
        try:
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            text = result["candidates"][0]["content"]["parts"][0]["text"]
            return _parse_json_response(text)

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.readable() else ""
            print(f"   [WARN] Gemini error (attempt {attempt+1}): {e.code} {error_body[:150]}")
            if e.code == 429:
                time.sleep(5)
                continue
            else:
                return None

        except Exception as e:
            print(f"   [WARN] Gemini request failed (attempt {attempt+1}): {e}")
            if attempt < 1:
                time.sleep(3)

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
        "temperature": 0.7,
        "max_tokens": 8192,
    }

    data = json.dumps(payload).encode("utf-8")

    for attempt in range(2):
        try:
            req = urllib.request.Request(
                OPENROUTER_URL, data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://konopla.ua",
                    "X-Title": "KONOPLA.UA"
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            text = result["choices"][0]["message"]["content"]
            return _parse_json_response(text)

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.readable() else ""
            print(f"   [WARN] {model} error (attempt {attempt+1}): {e.code} {error_body[:150]}")
            if e.code == 429:
                time.sleep(5)
                continue
            else:
                return None

        except Exception as e:
            print(f"   [WARN] Request failed (attempt {attempt+1}): {e}")
            if attempt < 1:
                time.sleep(3)

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

    required = ["title", "summary", "content", "category", "tags"]
    if not all(key in article_data for key in required):
        print(f"   [WARN] Missing fields: {list(article_data.keys())}")
        return None

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
