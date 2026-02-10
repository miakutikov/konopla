"""
images.py — Підбирає зображення для статей через Unsplash API

Unsplash безкоштовний: 50 запитів/годину на демо ключі.
При 8 статтях на запуск — вистачає з запасом.
"""

import json
import os
import urllib.request
import urllib.error
from config import UNSPLASH_ACCESS_KEY, CATEGORY_IMAGE_QUERIES


def get_unsplash_image(query, fallback_category="інше"):
    """
    Шукає зображення на Unsplash за запитом.
    
    Повертає dict з ключами:
        url: URL зображення (regular size, ~1080px)
        thumb: URL мініатюри
        author: Ім'я фотографа
        author_url: Посилання на профіль
        unsplash_url: Посилання на фото на Unsplash
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
            }
        )
        
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        results = data.get("results", [])
        if not results:
            print(f"[WARN] No Unsplash images found for: {search_query}")
            # Try fallback category query
            if query and fallback_category:
                fallback_query = CATEGORY_IMAGE_QUERIES.get(fallback_category, "hemp plant industrial")
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
        }
        
        # Trigger download event (required by Unsplash API guidelines)
        _trigger_download(image_data["download_url"], access_key)
        
        print(f"[OK] Image found: {search_query} → by {image_data['author']}")
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
            download_url,
            headers={"Authorization": f"Client-ID {access_key}"}
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass  # Non-critical


def format_image_credit(image_data):
    """Форматує кредит фотографа для статті (вимога Unsplash)."""
    if not image_data:
        return ""
    return (
        f'Фото: <a href="{image_data["author_url"]}?utm_source=konopla_ua&utm_medium=referral">'
        f'{image_data["author"]}</a> / '
        f'<a href="{image_data["unsplash_url"]}?utm_source=konopla_ua&utm_medium=referral">Unsplash</a>'
    )


def format_image_credit_md(image_data):
    """Markdown версія кредиту для Hugo статей."""
    if not image_data:
        return ""
    return (
        f'*Фото: [{image_data["author"]}]({image_data["author_url"]}?utm_source=konopla_ua&utm_medium=referral) / '
        f'[Unsplash]({image_data["unsplash_url"]}?utm_source=konopla_ua&utm_medium=referral)*'
    )


# Need to import urllib.parse for URL encoding
import urllib.parse


if __name__ == "__main__":
    # Test
    result = get_unsplash_image("hemp textile factory")
    if result:
        print(json.dumps(result, indent=2))
        print(format_image_credit_md(result))
    else:
        print("No API key or no results")
