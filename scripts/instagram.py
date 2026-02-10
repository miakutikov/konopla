"""
instagram.py — Генерує картинки для Instagram Stories

Створює зображення 1080x1920 з:
- Фоновим зображенням (або градієнтом якщо фото немає)
- Заголовком статті
- Категорією
- Логотипом Konopla.UA

Картинки зберігаються в static/instagram/ — можна завантажити і запостити вручну,
або підключити сервіс типу Later/Buffer для автопостингу.
"""

import os
import sys
import textwrap

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False


# Story dimensions
STORY_WIDTH = 1080
STORY_HEIGHT = 1920

# Colors
BG_COLOR_TOP = (27, 67, 50)      # dark green
BG_COLOR_BOTTOM = (45, 106, 79)  # medium green
ACCENT_COLOR = (82, 183, 136)    # light green
WHITE = (255, 255, 255)
OVERLAY_COLOR = (0, 0, 0, 140)   # semi-transparent black

# Category emoji map
EMOJI_MAP = {
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
    "інше": "📰",
}


def _get_font(size):
    """Шукає доступний шрифт."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _get_font_regular(size):
    """Шукає звичайний (не bold) шрифт."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _draw_gradient(draw, width, height, color_top, color_bottom):
    """Малює вертикальний градієнт."""
    for y in range(height):
        ratio = y / height
        r = int(color_top[0] + (color_bottom[0] - color_top[0]) * ratio)
        g = int(color_top[1] + (color_bottom[1] - color_top[1]) * ratio)
        b = int(color_top[2] + (color_bottom[2] - color_top[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def _wrap_text(text, font, max_width, draw):
    """Розбиває текст на рядки що вміщуються в ширину."""
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        text_width = bbox[2] - bbox[0]
        
        if text_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    
    if current_line:
        lines.append(current_line)
    
    return lines


def generate_story_image(title, category, summary="", image_url=None, output_dir="static/instagram"):
    """
    Генерує картинку для Instagram Story.
    
    Повертає шлях до файлу або None.
    """
    if not HAS_PILLOW:
        print("[WARN] Pillow not installed, skipping Instagram image generation")
        return None
    
    try:
        # Create image
        img = Image.new("RGB", (STORY_WIDTH, STORY_HEIGHT))
        draw = ImageDraw.Draw(img)
        
        # Background: gradient
        _draw_gradient(draw, STORY_WIDTH, STORY_HEIGHT, BG_COLOR_TOP, BG_COLOR_BOTTOM)
        
        # If we have a background image URL, we could download it
        # For now, using gradient (downloading in GitHub Actions would need urllib)
        
        # Accent line at top
        draw.rectangle([(0, 0), (STORY_WIDTH, 6)], fill=ACCENT_COLOR)
        
        # Logo area (top)
        font_logo = _get_font(42)
        draw.text((60, 80), "🌿 Konopla.UA", font=font_logo, fill=WHITE)
        
        # Thin divider
        draw.rectangle([(60, 150), (300, 152)], fill=ACCENT_COLOR)
        
        # Category badge
        emoji = EMOJI_MAP.get(category, "📰")
        font_category = _get_font_regular(32)
        category_text = f"{emoji}  {category.upper()}"
        draw.text((60, 200), category_text, font=font_category, fill=ACCENT_COLOR)
        
        # Main title — big, centered vertically
        font_title = _get_font(64)
        max_text_width = STORY_WIDTH - 120  # 60px padding each side
        
        title_lines = _wrap_text(title, font_title, max_text_width, draw)
        
        # Limit to 6 lines max
        if len(title_lines) > 6:
            title_lines = title_lines[:5]
            title_lines[-1] = title_lines[-1][:30] + "..."
        
        # Calculate total title height
        line_height = 80
        total_title_height = len(title_lines) * line_height
        
        # Start Y — vertically centered in middle zone
        title_start_y = (STORY_HEIGHT - total_title_height) // 2 - 50
        title_start_y = max(300, title_start_y)  # Don't overlap with header
        
        for i, line in enumerate(title_lines):
            y = title_start_y + i * line_height
            draw.text((60, y), line, font=font_title, fill=WHITE)
        
        # Summary (if provided, below title)
        if summary:
            font_summary = _get_font_regular(30)
            summary_y = title_start_y + total_title_height + 40
            summary_lines = _wrap_text(summary, font_summary, max_text_width, draw)[:3]
            for i, line in enumerate(summary_lines):
                draw.text((60, summary_y + i * 42), line, font=font_summary, fill=(200, 220, 210))
        
        # Bottom CTA
        cta_y = STORY_HEIGHT - 200
        
        # Swipe up hint
        font_cta = _get_font(28)
        draw.text((60, cta_y), "↑ Читати на konopla.ua", font=font_cta, fill=ACCENT_COLOR)
        
        # Bottom accent line
        draw.rectangle([(0, STORY_HEIGHT - 6), (STORY_WIDTH, STORY_HEIGHT)], fill=ACCENT_COLOR)
        
        # Save
        os.makedirs(output_dir, exist_ok=True)
        
        # Filename from title (transliterated)
        from publisher import slugify
        safe_name = slugify(title)[:50]
        
        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
        filename = f"story-{timestamp}-{safe_name}.png"
        filepath = os.path.join(output_dir, filename)
        
        img.save(filepath, "PNG", quality=95)
        print(f"[OK] Instagram story created: {filepath}")
        return filepath
        
    except Exception as e:
        print(f"[ERROR] Instagram story generation failed: {e}")
        return None


if __name__ == "__main__":
    # Test
    path = generate_story_image(
        title="Німеччина запускає найбільший завод з виробництва конопляного бетону",
        category="будівництво",
        summary="Новий завод у Баварії виробляє 500 тонн hempcrete на місяць",
        output_dir="/tmp/test_ig"
    )
    if path:
        print(f"Test image: {path}")
