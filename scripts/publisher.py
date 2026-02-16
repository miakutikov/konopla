"""
publisher.py — Створює Hugo markdown файли з переписаних новин
"""

import os
import re
from datetime import datetime, timezone


def slugify(text):
    """Створює URL-friendly slug з українського тексту."""
    # Transliteration map for Ukrainian
    translit = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'h', 'ґ': 'g', 'д': 'd', 'е': 'e',
        'є': 'ye', 'ж': 'zh', 'з': 'z', 'и': 'y', 'і': 'i', 'ї': 'yi', 'й': 'y',
        'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
        'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch',
        'ш': 'sh', 'щ': 'shch', 'ь': '', 'ю': 'yu', 'я': 'ya', 'ъ': '', 'ы': 'y',
        'э': 'e',
    }
    
    text = text.lower().strip()
    result = []
    for char in text:
        if char in translit:
            result.append(translit[char])
        elif char.isascii() and (char.isalnum() or char == '-'):
            result.append(char)
        elif char in (' ', '_', '.'):
            result.append('-')
    
    slug = '-'.join(filter(None, ''.join(result).split('-')))
    return slug[:80]  # Limit length


def create_article_file(article_data, source_url, source_name, image_data=None, content_dir="content/news"):
    """
    Створює Hugo markdown файл для статті.
    
    article_data: dict from Gemini (title, summary, content, category, tags)
    source_url: URL оригінальної статті
    source_name: назва джерела
    image_data: dict from Unsplash (url, author, author_url, unsplash_url) or None
    content_dir: папка для зберігання
    
    Повертає шлях до створеного файлу або None.
    """
    try:
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        date_prefix = now.strftime("%Y%m%d-%H%M")
        
        title = article_data["title"]
        summary = article_data["summary"]
        content = article_data["content"]
        category = article_data.get("category", "інше")
        tags = article_data.get("tags", [])
        
        slug = slugify(title)
        filename = f"{date_prefix}-{slug}.md"
        filepath = os.path.join(content_dir, filename)
        
        # Build front matter
        tags_str = ", ".join(f'"{tag}"' for tag in tags[:5])
        
        # Image lines
        image_line = ""
        image_credit = ""
        if image_data:
            image_line = f'image: "{image_data["url"]}"'
            image_credit = (
                f'image_author: "{image_data["author"]}"'
                f'\nimage_author_url: "{image_data["author_url"]}"'
                f'\nimage_source: "Unsplash"'
                f'\nimage_source_url: "{image_data["unsplash_url"]}"'
            )
        
        front_matter = f"""---
title: "{title.replace('"', "'")}"
date: {date_str}
summary: "{summary.replace('"', "'")}"
categories: ["{category}"]
tags: [{tags_str}]
source: "{source_name.replace('"', "'")}"
source_url: "{source_url}"
{image_line}
{image_credit}
draft: false
---

{content}
"""
        
        # Add image credit at the bottom if available
        if image_data:
            from images import format_image_credit_md
            credit = format_image_credit_md(image_data)
            if credit:
                front_matter += f"\n\n---\n{credit}\n"
        
        os.makedirs(content_dir, exist_ok=True)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(front_matter)
        
        print(f"[OK] Created: {filepath}")
        return filepath
        
    except Exception as e:
        print(f"[ERROR] Failed to create article file: {e}")
        return None


def create_telegram_message(article_data, site_url="https://konopla.ua"):
    """
    Формує повідомлення для Telegram-каналу.
    Повертає текст повідомлення.
    """
    title = article_data["title"]
    summary = article_data["summary"]
    category = article_data.get("category", "")
    slug = slugify(title)
    
    now = datetime.now(timezone.utc)
    date_prefix = now.strftime("%Y%m%d-%H%M")
    
    article_url = f"{site_url}/news/{date_prefix}-{slug}/"
    
    # Emoji per category
    emoji_map = {
        "текстиль": "🧵",
        "будівництво": "🏗️",
        "агро": "🌱",
        "біопластик": "♻️",
        "автопром": "🚗",
        "харчова": "🥗",
        "енергетика": "⚡",
        "косметика": "✨",
        "законодавство": "📋",
        "наука": "🔬",
        "інше": "📰",
    }
    emoji = emoji_map.get(category, "📰")
    
    message = f"""{emoji} <b>{title}</b>

{summary}

<a href="{article_url}">Читати повністю →</a>

🌿 @uakonopla"""
    
    return message


if __name__ == "__main__":
    # Test
    test_data = {
        "title": "Німеччина запускає завод з виробництва конопляного бетону",
        "summary": "Новий завод у Баварії виробляє блоки з конопляного бетону для житлового будівництва.",
        "content": "Тестовий контент статті.\n\nДругий абзац.",
        "category": "будівництво",
        "tags": ["конопляний бетон", "німеччина", "будівництво"]
    }
    
    filepath = create_article_file(test_data, "https://example.com", "Test Source")
    print(f"Created: {filepath}")
    
    msg = create_telegram_message(test_data)
    print(f"\nTelegram message:\n{msg}")
