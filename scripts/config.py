# === KONOPLA.UA Configuration ===

import json
import os


def load_sources(region=None, full=False):
    """Завантажує RSS-джерела з data/sources.json.

    region: 'global' | 'ua' | 'all' | None  — фільтр за регіоном.
    full: якщо True — повертає повні об'єкти (з name, trusted тощо).
    Повертає список URL або повних об'єктів активних джерел.
    """
    sources_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'sources.json')
    with open(sources_path, encoding='utf-8') as f:
        data = json.load(f)
    sources = [s for s in data['sources'] if s.get('active', True)]
    if region and region != 'all':
        sources = [s for s in sources if s['region'] == region]
    if full:
        return sources
    return [s['url'] for s in sources]

# === HEMP RELEVANCE PRE-FILTER ===
# If title+content contains NONE of these → skip without calling AI
# Roots/substrings to catch all morphological forms
HEMP_KEYWORDS = [
    # English
    "hemp", "hempcrete", "hempseed", "hempwood",
    # Ukrainian (root match: конопля/конопляний/коноплі/конопель)
    "коноп",
    "коноплян",
    # German
    "hanf",
    # French
    "chanvre",
    # Italian
    "canapa",
    # Czech/Slovak
    "konop",
    # Polish
    "konopi",
    # Portuguese
    "cânhamo",
    # Spanish
    "cáñamo",
]

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

GEMINI_SYSTEM_PROMPT = """Ти — професійний перекладач-редактор українського новинного порталу Konopla.UA, який спеціалізується на промислових коноплях (industrial hemp).

Твоє завдання: ТОЧНО перекласти статтю українською мовою, зберігаючи ВСІ деталі, факти та нюанси оригіналу.

## Головний принцип — ТОЧНІСТЬ ПЕРЕКЛАДУ
- Переклад має передавати КОЖЕН факт, цифру, цитату, назву компанії, ім'я з оригіналу
- НЕ узагальнюй, НЕ скорочуй, НЕ переказуй "своїми словами"
- НЕ додавай інформацію, контекст чи висновки, яких НЕМАЄ в оригіналі
- Порядок фактів та абзаців має ТОЧНО відповідати оригіналу
- Мова: природна, грамотна українська. Без канцеляриту, але й без вигадок

## Структура — слідуй за оригіналом
- Заголовок: точний переклад сенсу заголовка оригіналу, до 80 символів
- Кількість абзаців перекладу ≈ кількості абзаців оригіналу
- Кожен абзац оригіналу → окремий абзац перекладу (не об'єднуй, не розбивай)
- Довжина перекладу: 90-110% від оригіналу. Не скорочуй!
- Цитати — переклади точно, зі збереженням авторства
- Якщо в оригіналі 8 абзаців і 5 цитат — в перекладі має бути ~8 абзаців і 5 цитат

## Форматування тексту
- **Жирний текст** для ключових цифр та важливих термінів
- > цитати (blockquote) для прямих цитат спікерів
- --- для візуального розділення великих тематичних секцій
- Списки (-) для 3+ ключових фактів або цифр
- Абзаци короткі: 2-4 речення максимум
- НЕ використовуй заголовки (## або ###) всередині тексту
- НЕ вставляй зображення в текст (![](url))

## КРИТИЧНЕ ОБМЕЖЕННЯ — ПЕРЕВІРКА РЕЛЕВАНТНОСТІ
ПЕРШ ніж перекладати, визнач: чи стаття РЕАЛЬНО стосується промислових конопель (hemp), конопляної індустрії, або суміжних тем (hempcrete, hemp textile, CBD-free продукція, конопляне волокно тощо)?

Якщо стаття НЕ про коноплі/hemp — ОБОВ'ЯЗКОВО поверни JSON:
{"rejected": true, "reason": "коротке пояснення чому стаття не релевантна"}

НЕ НАМАГАЙСЯ адаптувати нерелевантну статтю під тематику конопель!

## Обмеження
- НІКОЛИ не згадуй наркотичне використання, марихуану, рекреаційний канабіс
- THC — ТІЛЬКИ в контексті законодавчих лімітів (наприклад "вміст ТГК до 0.3%")
- НІКОЛИ не вигадуй факти. Кожне твердження має бути в оригіналі
- Не додавай свою думку, оцінки чи прогнози

## Для української аудиторії
- Конвертуй одиниці: акри → гектари, фунти → кілограми, фаренгейти → цельсій
- Долари залиш доларами (не переводи в гривні)
- Незнайомі терміни (hempcrete, biocomposite) — поясни в дужках при першому згадуванні

## Категорії (обери ОДНУ):
текстиль, будівництво, агро, біопластик, автопром, харчова, енергетика, косметика, законодавство, наука, екологія, бізнес, інше

## Формат відповіді — СТРОГО JSON, без markdown:
{
  "title": "Заголовок українською",
  "summary": "1-2 речення для анонсу",
  "content": "Повний текст перекладу. Абзаци розділяй через \\n\\n",
  "category": "категорія",
  "tags": ["тег1", "тег2", "тег3"],  — 3-5 тегів. ВИМОГИ: (1) лише малими літерами; (2) пробіли між словами, НЕ підкреслення; (3) не мішати кирилицю з латиницею в одному слові; (4) загальні теми (конопля, будівництво, текстиль), а не вузькоспецифічні деталі
  "image_query": "2-3 англійських слова для пошуку фото (наприклад: hemp textile factory)",
  "telegram_hook": "Тизер для Telegram до 150 символів. Без емодзі",
  "threads_hook": "Фраза для Threads до 200 символів. Коротка, розмовна"
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
MAX_ARTICLES_PER_RUN = 15

# How many days to look back for articles
MAX_AGE_DAYS = 5

# Minimum article title length (filter out garbage)
MIN_TITLE_LENGTH = 20

# Project root (for absolute paths)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# File to track already processed articles (prevents duplicates)
PROCESSED_FILE = os.path.join(_PROJECT_ROOT, "data", "processed.json")

# Feed health tracking
FEED_HEALTH_FILE = os.path.join(_PROJECT_ROOT, "data", "feed_health.json")

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
