"""
images.py — Генерація та підбір зображень для статей

Пріоритет:
1. Gemini Image Generation (gemini-2.5-flash-image) — AI-генерація унікальних зображень
2. Unsplash API — стокові фото як fallback

Gemini free tier: 2 зображення/хвилину, 500/день
Unsplash free tier: 50 запитів/годину
"""

import base64
import json
import os
import time
import urllib.request
import urllib.error
import urllib.parse

from config import UNSPLASH_ACCESS_KEY, CATEGORY_IMAGE_QUERIES


# ---------------------------------------------------------------------------
# Gemini Image Generation (NanoBanana)
# ---------------------------------------------------------------------------

GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_IMAGE_MODEL}:generateContent"
)

# Prompt template for hemp industry images
GEMINI_IMAGE_PROMPT = (
    "Generate a high-quality photo-realistic image for a news article. "
    "The image MUST be in wide landscape format with exact 16:9 aspect ratio (1280x720 resolution). "
    "Make it look professional, cinematic, suitable for a premium news website about industrial hemp. "
    "Do NOT include any text, watermarks, logos, or UI elements in the image. "
    "Topic: {query}"
)


def generate_gemini_image(query, article_id="img"):
    """
    Генерує зображення через Gemini Image Generation API.

    Повертає dict сумісний з image_data форматом:
        url: відносний шлях до зображення (для Hugo)
        thumb: той самий шлях
        author: "AI Generated"
        author_url: ""
        unsplash_url: ""
        source: "gemini"
        local_path: абсолютний шлях до файлу
    Або None якщо помилка.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")

    if not api_key:
        print("[INFO] GEMINI_API_KEY not set, skipping Gemini image generation")
        return None

    prompt = GEMINI_IMAGE_PROMPT.format(query=query)

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }

    try:
        url = f"{GEMINI_API_URL}?key={api_key}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        print(f"   🎨 Generating image via Gemini: {query[:60]}...")
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        # Extract image from response
        parts = result.get("candidates", [{}])[0].get("content", {}).get("parts", [])

        image_b64 = None
        mime_type = "image/png"
        for part in parts:
            if "inlineData" in part:
                image_b64 = part["inlineData"]["data"]
                mime_type = part["inlineData"].get("mimeType", "image/png")
                break

        if not image_b64:
            print("[WARN] Gemini returned no image data")
            return None

        # Determine file extension
        ext = "png" if "png" in mime_type else "jpg"

        # Save to static/images/generated/ (use project root)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        gen_dir = os.path.join(project_root, "static", "images", "generated")
        os.makedirs(gen_dir, exist_ok=True)

        filename = f"{article_id}.{ext}"
        filepath = os.path.join(gen_dir, filename)

        image_bytes = base64.b64decode(image_b64)

        # Post-process: enforce 16:9 aspect ratio (1280x720)
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(image_bytes))
            target_ratio = 16 / 9
            current_ratio = img.width / img.height

            if abs(current_ratio - target_ratio) > 0.05:  # Only crop if significantly off
                if current_ratio > target_ratio:
                    # Too wide — crop sides
                    new_width = int(img.height * target_ratio)
                    left = (img.width - new_width) // 2
                    img = img.crop((left, 0, left + new_width, img.height))
                else:
                    # Too tall — crop top/bottom
                    new_height = int(img.width / target_ratio)
                    top = (img.height - new_height) // 2
                    img = img.crop((0, top, img.width, top + new_height))

            # Resize to standard 1280x720
            img = img.resize((1280, 720), Image.LANCZOS)

            # Save as optimized JPEG for smaller file size
            ext = "jpg"
            filename = f"{article_id}.{ext}"
            filepath = os.path.join(gen_dir, filename)
            img.save(filepath, "JPEG", quality=88, optimize=True)

            with open(filepath, "rb") as f:
                image_bytes = f.read()

            print(f"   ✅ Image cropped to 16:9 (1280x720)")
        except ImportError:
            print("   [INFO] Pillow not available, saving raw image")
            with open(filepath, "wb") as f:
                f.write(image_bytes)

        size_kb = len(image_bytes) / 1024
        print(f"   ✅ Gemini image saved: {filepath} ({size_kb:.0f} KB)")

        # Return image_data compatible dict
        # Hugo uses relative path from static/
        relative_url = f"/images/generated/{filename}"

        # local_path: relative from project root (for git add + Telegram photo upload)
        relative_path = os.path.join("static", "images", "generated", filename)

        return {
            "url": relative_url,
            "thumb": relative_url,
            "author": "AI Generated",
            "author_url": "",
            "unsplash_url": "",
            "source": "gemini",
            "local_path": relative_path,
        }

    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode("utf-8")[:300]
        except Exception:
            pass
        print(f"[WARN] Gemini image API error {e.code}: {error_body}")
        return None
    except Exception as e:
        print(f"[WARN] Gemini image generation failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Unsplash (fallback)
# ---------------------------------------------------------------------------


def get_unsplash_image(query, fallback_category="інше"):
    """
    Шукає зображення на Unsplash за запитом.

    Повертає dict з ключами:
        url: URL зображення (regular size, ~1080px)
        thumb: URL мініатюри
        author: Ім'я фотографа
        author_url: Посилання на профіль
        unsplash_url: Посилання на фото на Unsplash
        source: "unsplash"
    Або None якщо помилка.
    """
    access_key = os.environ.get("UNSPLASH_ACCESS_KEY", UNSPLASH_ACCESS_KEY)

    if not access_key:
        print("[WARN] UNSPLASH_ACCESS_KEY not set, skipping image")
        return None

    # Build search URL
    search_query = query or CATEGORY_IMAGE_QUERIES.get(fallback_category, "hemp plant")
    encoded_query = urllib.parse.quote(search_query)
    url = (
        f"https://api.unsplash.com/search/photos"
        f"?query={encoded_query}"
        f"&per_page=1"
        f"&orientation=landscape"
        f"&content_filter=high"
    )

    try:
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Client-ID {access_key}",
                "Accept-Version": "v1",
            },
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        results = data.get("results", [])
        if not results:
            print(f"[WARN] No Unsplash images found for: {search_query}")
            # Try fallback category query
            if query and fallback_category:
                fallback_query = CATEGORY_IMAGE_QUERIES.get(
                    fallback_category, "hemp plant industrial"
                )
                if fallback_query != query:
                    print(f"[INFO] Trying fallback query: {fallback_query}")
                    return get_unsplash_image(fallback_query, fallback_category=None)
            return None

        photo = results[0]

        image_data = {
            "url": photo["urls"]["regular"],
            "thumb": photo["urls"]["small"],
            "author": photo["user"]["name"],
            "author_url": photo["user"]["links"]["html"],
            "unsplash_url": photo["links"]["html"],
            "download_url": photo["links"]["download_location"],
            "source": "unsplash",
        }

        # Trigger download event (required by Unsplash API guidelines)
        _trigger_download(image_data["download_url"], access_key)

        print(f"   ✅ Unsplash image: {search_query} → by {image_data['author']}")
        return image_data

    except urllib.error.HTTPError as e:
        print(f"[WARN] Unsplash API error: {e.code}")
        return None
    except Exception as e:
        print(f"[WARN] Unsplash request failed: {e}")
        return None


def _trigger_download(download_url, access_key):
    """Повідомляє Unsplash про використання фото (обов'язково за правилами API)."""
    try:
        req = urllib.request.Request(
            download_url, headers={"Authorization": f"Client-ID {access_key}"}
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass  # Non-critical


# ---------------------------------------------------------------------------
# Unified image getter: Gemini first, Unsplash fallback
# ---------------------------------------------------------------------------


def get_article_image(query, fallback_category="інше", article_id="img"):
    """
    Отримує зображення для статті.
    Спочатку пробує Gemini (AI-генерація), потім Unsplash (стокові фото).

    query: текстовий запит (image_query від rewriter)
    fallback_category: категорія статті для fallback запиту
    article_id: ID статті для назви файлу

    Повертає image_data dict або None.
    """
    # 1. Try Gemini Image Generation
    image_data = generate_gemini_image(query, article_id=article_id)
    if image_data:
        return image_data

    # Small delay before fallback to avoid rate issues
    time.sleep(1)

    # 2. Fallback to Unsplash
    print("   🔄 Falling back to Unsplash...")
    image_data = get_unsplash_image(query, fallback_category=fallback_category)
    return image_data


# ---------------------------------------------------------------------------
# Image credits formatting
# ---------------------------------------------------------------------------


def format_image_credit(image_data):
    """Форматує кредит для HTML (Telegram, тощо)."""
    if not image_data:
        return ""
    if image_data.get("source") == "gemini":
        return "🎨 Зображення згенеровано AI"
    return (
        f'Фото: <a href="{image_data["author_url"]}?utm_source=konopla_ua&utm_medium=referral">'
        f'{image_data["author"]}</a> / '
        f'<a href="{image_data["unsplash_url"]}?utm_source=konopla_ua&utm_medium=referral">Unsplash</a>'
    )


def format_image_credit_md(image_data):
    """Markdown версія кредиту для Hugo статей."""
    if not image_data:
        return ""
    if image_data.get("source") == "gemini":
        return "*🎨 Зображення згенеровано AI*"
    return (
        f'*Фото: [{image_data["author"]}]({image_data["author_url"]}?utm_source=konopla_ua&utm_medium=referral) / '
        f'[Unsplash]({image_data["unsplash_url"]}?utm_source=konopla_ua&utm_medium=referral)*'
    )


if __name__ == "__main__":
    # Test Gemini
    print("=== Testing Gemini Image Generation ===")
    result = generate_gemini_image("industrial hemp textile factory", article_id="test")
    if result:
        print(json.dumps({k: v for k, v in result.items() if k != "local_path"}, indent=2))
    else:
        print("Gemini failed or no API key")

    print("\n=== Testing Unsplash ===")
    result = get_unsplash_image("hemp textile factory")
    if result:
        print(json.dumps(result, indent=2))
        print(format_image_credit_md(result))
    else:
        print("No API key or no results")
