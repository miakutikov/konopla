"""
publisher.py — Створює Hugo markdown файли з переписаних новин
"""

import glob
import os
import re
import tempfile
from datetime import datetime, timezone
from difflib import SequenceMatcher

# === Tag normalization & canonicalization ===

_existing_tags_cache = None


def _normalize_tag(tag):
    """Нормалізує один тег: lowercase, пробіли, фільтр сміття."""
    if not isinstance(tag, str):
        return None
    tag = tag.strip().lower()
    tag = tag.replace('_', ' ')
    tag = re.sub(r'\s+', ' ', tag).strip()
    if not tag or len(tag) < 2:
        return None
    # Відкидаємо слова з мікс-скриптом (кирилиця + латиниця в одному слові)
    for word in tag.split():
        has_cyr = bool(re.search(r'[а-яіїєґ]', word))
        has_lat = bool(re.search(r'[a-z]', word))
        if has_cyr and has_lat:
            return None
    return tag


def _load_existing_tags(content_dir):
    """Читає всі наявні теги з .md файлів у content_dir."""
    tags = set()
    for filepath in glob.glob(os.path.join(content_dir, '*.md')):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                head = f.read(2000)
            m = re.search(r'^tags:\s*\[([^\]]*)\]', head, re.MULTILINE)
            if m:
                for t in re.findall(r'"([^"]+)"', m.group(1)):
                    norm = _normalize_tag(t)
                    if norm:
                        tags.add(norm)
        except Exception:
            continue
    return tags


def _canonicalize_tag(norm_tag, existing_tags):
    """Повертає найближчий існуючий тег або norm_tag як новий."""
    if norm_tag in existing_tags:
        return norm_tag
    best, best_score = None, 0.0
    for existing in existing_tags:
        score = SequenceMatcher(None, norm_tag, existing).ratio()
        if score > best_score:
            best_score = score
            best = existing
    if best_score >= 0.85:
        print(f"[TAGS] '{norm_tag}' → '{best}' ({best_score:.2f})")
        return best
    return norm_tag


def process_tags(raw_tags, content_dir):
    """Нормалізує та каталогізує теги: використовує існуючі, нові — тільки якщо потрібно."""
    global _existing_tags_cache
    if _existing_tags_cache is None:
        _existing_tags_cache = _load_existing_tags(content_dir)

    result, seen = [], set()
    for tag in raw_tags:
        norm = _normalize_tag(tag)
        if not norm:
            continue
        canonical = _canonicalize_tag(norm, _existing_tags_cache)
        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)

    # Поповнюємо кеш новими тегами для наступних статей у тому ж запуску
    _existing_tags_cache.update(result)
    return result[:5]


def fix_double_utf8(text):
    """
    Fix double-encoded UTF-8 text.

    When UTF-8 bytes are mistakenly interpreted as Latin-1 and then
    re-encoded to UTF-8, we get sequences like c3 90 c2 92 instead of d0 92.
    This function detects and reverses that process.

    Safe to call on already-correct text — returns it unchanged.
    """
    if not isinstance(text, str):
        return text
    try:
        # Try to encode as Latin-1: this only succeeds if every character
        # is in the 0x00-0xFF range (which is the symptom of double-encoding).
        raw = text.encode('latin-1')
        # Now decode those bytes as UTF-8 to recover the original text.
        fixed = raw.decode('utf-8')
        return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        # Not double-encoded — return as-is
        return text


def fix_article_encoding(article_data):
    """Apply fix_double_utf8 to all text fields in article data."""
    fixed = dict(article_data)
    for key in ('title', 'summary', 'content', 'category', 'telegram_hook', 'threads_hook', 'youtube_id'):
        if key in fixed and isinstance(fixed[key], str):
            fixed[key] = fix_double_utf8(fixed[key])
    if 'tags' in fixed and isinstance(fixed['tags'], list):
        fixed['tags'] = [fix_double_utf8(t) if isinstance(t, str) else t for t in fixed['tags']]
    return fixed


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


def create_article_file(article_data, source_url, source_name, image_data=None, content_dir="content/news", draft=False):
    """
    Створює Hugo markdown файл для статті.

    article_data: dict from Gemini (title, summary, content, category, tags)
    source_url: URL оригінальної статті
    source_name: назва джерела
    image_data: dict from Unsplash (url, author, author_url, unsplash_url) or None
    content_dir: папка для зберігання
    draft: якщо True, стаття створюється як чернетка (draft: true)
    
    Повертає шлях до створеного файлу або None.
    """
    try:
        # Fix potential double-encoded UTF-8 from pipeline
        article_data = fix_article_encoding(article_data)

        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        date_prefix = now.strftime("%Y%m%d-%H%M%S")

        title = article_data["title"]
        summary = article_data["summary"]
        content = article_data["content"]
        category = article_data.get("category", "інше")
        tags = process_tags(article_data.get("tags", []), content_dir)
        
        slug = slugify(title)
        filename = f"{date_prefix}-{slug}.md"
        filepath = os.path.join(content_dir, filename)
        
        # Build front matter
        tags_str = ", ".join(f'"{tag}"' for tag in tags[:5])
        
        # Image lines
        image_line = ""
        image_credit = ""
        if image_data:
            safe_url = image_data["url"].replace(chr(34), chr(39))
            image_line = f'image: "{safe_url}"'
            img_source = image_data.get("source", "unsplash")
            if img_source == "gemini":
                image_credit = (
                    f'image_source: "AI Generated"'
                )
            elif img_source == "original":
                image_credit = (
                    f'image_source: "Original"'
                )
            else:
                safe_author = image_data.get("author", "").replace(chr(34), chr(39))
                image_credit = (
                    f'image_author: "{safe_author}"'
                    f'\nimage_author_url: "{image_data.get("author_url", "")}"'
                    f'\nimage_source: "Unsplash"'
                    f'\nimage_source_url: "{image_data.get("unsplash_url", "")}"'
                )
        
        # Build front matter lines
        fm_lines = [
            "---",
            f'title: "{title.replace(chr(34), chr(39))}"',
            f"date: {date_str}",
            f'summary: "{summary.replace(chr(34), chr(39))}"',
            f'categories: ["{category}"]',
            f"tags: [{tags_str}]",
            f'source: "{source_name.replace(chr(34), chr(39))}"',
            f'source_url: "{source_url}"',
        ]
        if image_line:
            fm_lines.append(image_line)
        if image_credit:
            fm_lines.append(image_credit)
        # YouTube video ID (optional)
        youtube_id = article_data.get("youtube_id", "")
        if youtube_id:
            fm_lines.append(f'youtube_id: "{youtube_id}"')

        # Social media hooks (optional, from Gemini)
        telegram_hook = article_data.get("telegram_hook", "")
        if telegram_hook:
            fm_lines.append(f'telegram_hook: "{telegram_hook.replace(chr(34), chr(39))}"')
        threads_hook = article_data.get("threads_hook", "")
        if threads_hook:
            fm_lines.append(f'threads_hook: "{threads_hook.replace(chr(34), chr(39))}"')

        fm_lines.append(f"draft: {'true' if draft else 'false'}")
        fm_lines.append("---")
        fm_lines.append("")
        # Strip any hallucinated inline image URLs from AI
        content = re.sub(r'!\[.*?\]\(https?://[^\)]+\)', '', content).strip()
        fm_lines.append(content)
        fm_lines.append("")

        front_matter = "\n".join(fm_lines)
        
        # Add image credit at the bottom if available
        if image_data:
            from images import format_image_credit_md
            credit = format_image_credit_md(image_data)
            if credit:
                front_matter += f"\n\n---\n{credit}\n"
        
        os.makedirs(content_dir, exist_ok=True)

        tmp_fd, tmp_path = tempfile.mkstemp(dir=content_dir, suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(front_matter)
            os.replace(tmp_path, filepath)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

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
    article_data = fix_article_encoding(article_data)
    title = article_data["title"]
    summary = article_data["summary"]
    category = article_data.get("category", "")
    slug = slugify(title)
    
    now = datetime.now(timezone.utc)
    date_prefix = now.strftime("%Y%m%d-%H%M%S")

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
        "екологія": "🌍",
        "бізнес": "💼",
        "відео": "🎬",
        "інше": "📰",
    }
    emoji = emoji_map.get(category, "📰")
    
    message = f"""{emoji} <b>{title}</b>

{summary}

<a href="{article_url}">Читати повністю →</a>"""
    
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
