"""
rewriter.py — Переписує новини українською через OpenRouter API (безкоштовні моделі)
"""

import json
import os
import re
import time
import urllib.request
import urllib.error
from config import GEMINI_SYSTEM_PROMPT


API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Безкоштовні моделі — пробуємо по черзі, якщо одна недоступна
MODELS = [
    "google/gemma-3n-e4b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "z-ai/glm-4.5-air:free",
]


def rewrite_article(title, summary, source_url):
    """
    Відправляє статтю в OpenRouter API і отримує рерайт українською.
    Пробує кілька моделей по черзі.
    Повертає dict або None.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", API_KEY)
    if not api_key:
        print("[ERROR] OPENROUTER_API_KEY not set")
        return None

    user_prompt = f"""Перепиши цю новину:

Заголовок: {title}

Зміст: {summary}

Джерело: {source_url}"""

    for model in MODELS:
        result = _try_model(api_key, model, user_prompt)
        if result is not None:
            return result

    print("[ERROR] All models failed")
    return None


def _try_model(api_key, model, user_prompt):
    """Пробує одну модель, повертає dict або None."""
    print(f"   🤖 Model: {model}")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": GEMINI_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 2048,
    }

    data = json.dumps(payload).encode("utf-8")

    for attempt in range(2):
        try:
            req = urllib.request.Request(
                API_URL,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://konopla.ua",
                    "X-Title": "Konopla.UA News Pipeline"
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            text = result["choices"][0]["message"]["content"]

            # Clean up markdown code blocks
            text = re.sub(r"^```json\s*", "", text.strip())
            text = re.sub(r"\s*```$", "", text.strip())

            article_data = json.loads(text)

            required = ["title", "summary", "content", "category", "tags"]
            if not all(key in article_data for key in required):
                print(f"   [WARN] Missing fields: {list(article_data.keys())}")
                return None

            print(f"   ✅ OK")
            return article_data

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.readable() else ""
            print(f"   [WARN] {model} error (attempt {attempt+1}): {e.code} {error_body[:150]}")
            if e.code == 429:
                time.sleep(5)
                continue  # retry
            else:
                return None  # try next model

        except json.JSONDecodeError as e:
            print(f"   [WARN] JSON parse error (attempt {attempt+1}): {e}")
            if attempt < 1:
                time.sleep(2)

        except Exception as e:
            print(f"   [WARN] Request failed (attempt {attempt+1}): {e}")
            if attempt < 1:
                time.sleep(3)

    return None


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
