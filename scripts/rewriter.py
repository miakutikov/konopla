"""
rewriter.py — Переписує новини українською через Gemini API
"""

import json
import os
import re
import time
import urllib.request
import urllib.error
from config import GEMINI_SYSTEM_PROMPT


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"


def rewrite_article(title, summary, source_url):
    """
    Відправляє статтю в Gemini API і отримує рерайт українською.
    Повертає dict з ключами: title, summary, content, category, tags
    Або None якщо помилка.
    """
    if not GEMINI_API_KEY:
        print("[ERROR] GEMINI_API_KEY not set")
        return None
    
    # Update URL with actual key (in case env was loaded after module import)
    api_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key}"
    
    user_prompt = f"""Перепиши цю новину:

Заголовок: {title}

Зміст: {summary}

Джерело: {source_url}"""

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{GEMINI_SYSTEM_PROMPT}\n\n{user_prompt}"}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048,
        }
    }
    
    data = json.dumps(payload).encode("utf-8")
    
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            
            # Extract text from Gemini response
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            
            # Clean up: remove markdown code blocks if present
            text = re.sub(r"^```json\s*", "", text.strip())
            text = re.sub(r"\s*```$", "", text.strip())
            
            # Parse JSON
            article_data = json.loads(text)
            
            # Validate required fields
            required = ["title", "summary", "content", "category", "tags"]
            if not all(key in article_data for key in required):
                print(f"[WARN] Missing fields in Gemini response: {article_data.keys()}")
                return None
            
            return article_data
            
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.readable() else ""
            print(f"[WARN] Gemini API error (attempt {attempt+1}): {e.code} {error_body[:200]}")
            if e.code == 429:  # Rate limited
                time.sleep(10 * (attempt + 1))
            elif e.code >= 500:
                time.sleep(5)
            else:
                return None
                
        except json.JSONDecodeError as e:
            print(f"[WARN] Failed to parse Gemini response as JSON (attempt {attempt+1}): {e}")
            if attempt < 2:
                time.sleep(2)
                
        except Exception as e:
            print(f"[WARN] Gemini request failed (attempt {attempt+1}): {e}")
            if attempt < 2:
                time.sleep(3)
    
    return None


if __name__ == "__main__":
    # Test
    result = rewrite_article(
        "Hemp concrete blocks now available for European construction market",
        "A new factory in Germany has started mass production of hempcrete blocks for residential construction. The blocks are carbon-negative and provide excellent insulation.",
        "https://example.com/test"
    )
    if result:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Rewrite failed")
