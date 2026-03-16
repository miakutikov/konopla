# === KONOPLA.UA Configuration ===

import json
import os


def load_sources(region=None):
    """Завантажує RSS-джерела з data/sources.json.

    region: 'global' | 'ua' | 'all' | None  — фільтр за регіоном.
    Повертає список URL активних джерел.
    """
    sources_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'sources.json')
    with open(sources_path, encoding='utf-8') as f:
        data = json.load(f)
    sources = [s for s in data['sources'] if s.get('active', True)]
    if region and region != 'all':
        sources = [s for s in sources if s['region'] == region]
    return [s['url'] for s in sources]

# === CONTENT FILTERING ===

# Stop words — if ANY of these appear in title or content, article is REJECTED
STOP_WORDS = [
    # Drug / recreational
    "marijuana", "marihuana", "марихуана", "марихуани",
    "recreational cannabis", "recreational use",
    "weed", "ganja", "ганжа", "ганджа",
    "stoner", "stoned", "420", "4:20",
    "dispensary", "dispensaries", "диспансер",
    "psychoactive", "психоактивн",
    "narcotic", "наркотик", "наркотичн",
    "drug enforcement", "drug trafficking", "drug bust",
    "наркозасоб", "наркоторгів",
    "edible cannabis", "cannabis edible",
    "high potency", "get high", "getting high",
    "legalize recreational", "recreational legalization",
    "overdose", "передозуван",
    "intoxicat", "інтоксикац",
    "hallucin", "галюцинац",
    # Consumption methods
    "vape", "vaping", "вейп",
    "smoking weed", "smoke weed", "smoke marijuana",
    "joint", "joints", "джойнт",
    "bong", "bongs",
    "dab", "dabbing",
    "blunt", "blunts",
    # THC products
    "thc oil", "thc gummies", "thc edible",
    "thc concentrate", "thc cartridge",
    "delta-8", "delta-9 thc product",
    # Medical marijuana (separate from industrial)
    "medical marijuana", "mmj", "medical cannabis dispensary",
    "cannabis strain", "indica", "sativa",
]

# Context-aware: these are individual words that ONLY trigger rejection
# when NOT accompanied by industrial/allow context
SOFT_STOP_WORDS = [
    "thc", "тгк",
    "drug", "drugs",
    "smoking", "smoke",
    "cannabis",
    "cbd",
]

# Allow words — presence of these overrides soft_stop_words
ALLOW_CONTEXT = [
    "industrial hemp", "industrial cannabis",
    "hemp fiber", "hemp fibre",
    "hemp seed", "hempseed",
    "hempcrete", "hemp concrete",
    "hemp textile", "hemp fabric",
    "hemp building", "hemp construction",
    "hemp plastic", "hemp bioplastic",
    "hemp paper", "hemp pulp",
    "hemp composite", "hemp biocomposite",
    "hemp protein", "hemp nutrition",
    "hemp oil nutrition", "hemp seed oil",
    "hemp insulation",
    "hemp battery", "hemp supercapacitor",
    "hemp crop", "hemp farming", "hemp cultivation",
    "hemp fashion", "hemp clothing",
    "hemp packaging",
    "cbd-free", "thc-free",
    "0.3% thc", "0.2% thc",  # legal limit references
    "below thc limit", "under thc limit",
    "non-psychoactive",
    "farm bill",
    "fiber hemp", "fibre hemp",
    "декоративні коноплі", "технічні коноплі", "промислові коноплі",
]

# === GEMINI PROMPT ===

GEMINI_SYSTEM_PROMPT = """Ти — досвідчений редактор українського новинного порталу Konopla.UA, який спеціалізується на промислових коноплях (industrial hemp).

Твоє завдання: переписати англомовну новину українською мовою для української аудиторії.

## Стиль написання
- Пиши як сучасний український журналіст, НЕ як перекладач
- Мова жива, зрозуміла, без канцеляриту і "водянистих" фраз
- Перше речення має чіпляти — починай з факту або цифри, не з "Нещодавно стало відомо..."
- Коротші речення краще за довгі. Один абзац = одна думка
- Якщо є цифри, дати, імена компаній — обов'язково збережи

## Структура
- Заголовок: чіткий, інформативний, до 80 символів. Без клікбейту
- Текст: РОЗГОРНУТИЙ, довжина має відповідати оригіналу (±20%). Це повноцінна стаття, НЕ короткий анонс!
- ЗБЕРЕЖИ структуру оригіналу: порядок абзаців, порядок фактів, логіку викладу
- НЕ переставляй факти місцями, НЕ об'єднуй абзаци, НЕ пропускай інформацію
- Якщо в оригіналі 5 абзаців — в перекладі має бути ~5 абзаців. Якщо 10 — то ~10
- Перший абзац: головна новина (хто, що, де, коли)
- Далі: деталі, подробиці, цитати, цифри — все що є в оригіналі, в тому ж порядку
- Контекст: якщо в оригіналі є пояснення ситуації — збережи його. НЕ додавай контекст від себе
- Останній абзац: чому це важливо / що це означає для індустрії
- ВАЖЛИВО: збережи ВСІ факти, деталі та цифри з оригіналу. Не скорочуй, а перепиши повністю

## Форматування тексту (ВАЖЛИВО для візуальної привабливості!)
- Використовуй **жирний текст** для ключових фактів, цифр та важливих термінів (наприклад: **3,5 мільярди доларів**, **новий рекорд**)
- Використовуй > цитати (blockquote) для прямих цитат спікерів — виділяй їх окремими блоками
- Додавай --- (горизонтальну лінію) для візуального розділення великих тематичних секцій
- Якщо є 3+ ключових цифри або факти, оформлюй їх як список з маркерами (-)
- Перший абзац має бути найсильнішим — починай з головного факту чи цифри
- НЕ використовуй заголовки (## або ###) всередині тексту
- Абзаци короткі: 2-4 речення максимум
- Якщо надано оригінальні зображення — вбудуй 1-3 найкращих між абзацами у форматі: ![короткий опис](URL)
- Не ставь зображення на самому початку (там буде hero image)

## КРИТИЧНЕ ОБМЕЖЕННЯ — ПЕРЕВІРКА РЕЛЕВАНТНОСТІ
ПЕРШ ніж писати статтю, визнач: чи оригінальна стаття РЕАЛЬНО стосується промислових конопель (hemp), конопляної індустрії, або суміжних тем (hempcrete, hemp textile, CBD-free продукція, конопляне волокно тощо)?

Якщо стаття НЕ про коноплі/hemp — ОБОВ'ЯЗКОВО поверни JSON:
{"rejected": true, "reason": "стаття не стосується промислових конопель"}

НЕ НАМАГАЙСЯ адаптувати нерелевантну статтю під тематику конопель! Стаття про яблука, пшеницю, сонячні панелі чи будь-що інше НЕ стає статтею про коноплі.

## Обмеження
- НІКОЛИ не згадуй наркотичне використання, марихуану, рекреаційний канабіс
- THC можна згадувати ТІЛЬКИ в контексті законодавчих лімітів (наприклад "вміст ТГК до 0.3%")
- НІКОЛИ не вигадуй факти, яких немає в оригіналі. Кожне твердження має бути підтверджене оригінальним текстом
- Не додавай свою думку
- Не додавай інформацію про коноплі, якої немає в оригіналі — пиши ТІЛЬКИ те, що є в джерелі

## Для української аудиторії
- Конвертуй одиниці: акри → гектари, фунти → кілограми, фаренгейти → цельсій
- Долари залиш доларами (не переводи в гривні, курс змінюється)
- Незнайомі терміни (hempcrete, biocomposite) — поясни в дужках при першому згадуванні

## Категорії (обери ОДНУ найбільш точну):
текстиль, будівництво, агро, біопластик, автопром, харчова, енергетика, косметика, законодавство, наука, екологія, бізнес, інше

## Формат відповіді — СТРОГО JSON, без markdown, без зайвого тексту:
{
  "title": "Заголовок українською",
  "summary": "1-2 речення для анонсу в Telegram та на головній сторінці",
  "content": "Повний текст статті. Абзаци розділяй через \\n\\n",
  "category": "категорія",
  "tags": ["тег1", "тег2", "тег3"],
  "image_query": "2-3 англійських слова для пошуку фото на Unsplash (наприклад: hemp textile factory)",
  "telegram_hook": "Інтригуюче речення-тизер для Telegram (до 150 символів). Мета — змусити клікнути і прочитати повну статтю. Без емодзі. Приклад: Техас запустив першу повністю американську конопляну сорочку — і вона вже розпродана",
  "threads_hook": "Захоплююча фраза для Threads (до 200 символів). Коротка, розмовна, як пост у соцмережі. Мета — зацікавити і направити на сайт. Приклад: Уявіть бетон, який поглинає CO₂ замість того щоб його створювати. Конопляний хемпкріт саме це робить 🌱"
}"""

# === UNSPLASH ===
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")

# Fallback image queries per category (if Gemini doesn't suggest one)
CATEGORY_IMAGE_QUERIES = {
    "текстиль": "hemp textile fabric",
    "будівництво": "hempcrete construction building",
    "агро": "hemp field agriculture",
    "біопластик": "bioplastic hemp material",
    "автопром": "car interior natural fiber",
    "харчова": "hemp seeds food nutrition",
    "енергетика": "green energy sustainable",
    "косметика": "natural cosmetics hemp",
    "законодавство": "legislation law document",
    "наука": "laboratory research science",
    "екологія": "sustainability green nature",
    "бізнес": "business industry factory",
    "інше": "hemp plant industrial",
}

# === PIPELINE SETTINGS ===

# How many articles to process per run
MAX_ARTICLES_PER_RUN = 8

# How many days to look back for articles
MAX_AGE_DAYS = 3

# Minimum article title length (filter out garbage)
MIN_TITLE_LENGTH = 20

# Project root (for absolute paths)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# File to track already processed articles (prevents duplicates)
PROCESSED_FILE = os.path.join(_PROJECT_ROOT, "data", "processed.json")

# Pending articles awaiting moderation
PENDING_FILE = os.path.join(_PROJECT_ROOT, "data", "pending.json")

# Telegram offset for moderator polling
TELEGRAM_OFFSET_FILE = os.path.join(_PROJECT_ROOT, "data", "telegram_offset.json")

# Auto-reject pending articles after N hours
PENDING_MAX_AGE_HOURS = 48

# Semantic deduplication threshold (0.0 - 1.0)
SIMILARITY_THRESHOLD = 0.6

# Delay between API calls (seconds) to stay within free tier
API_DELAY_SECONDS = 5

# Delay between Telegram messages (seconds)
TELEGRAM_DELAY_SECONDS = 3
