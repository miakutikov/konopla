# === KONOPLA.UA Configuration ===

import os

# RSS feeds — industrial hemp news sources
RSS_FEEDS = [
    # === Dedicated hemp industry media ===
    "https://www.hemptodaymag.com/feed/",
    "https://hempbuildermag.com/feed/",
    "https://hempgazette.com/feed/",
    
    # === Google News — specific industrial hemp queries ===
    # Technology & Innovation
    "https://news.google.com/rss/search?q=industrial+hemp+technology&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=hemp+innovation+research&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=hemp+patent+invention&hl=en&gl=US&ceid=US:en",
    
    # Textile & Fashion
    "https://news.google.com/rss/search?q=hemp+textile+fabric+clothing&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=hemp+fashion+sustainable&hl=en&gl=US&ceid=US:en",
    
    # Construction
    "https://news.google.com/rss/search?q=hempcrete+hemp+construction+building&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=hemp+insulation+building+material&hl=en&gl=US&ceid=US:en",
    
    # Bioplastic & Materials
    "https://news.google.com/rss/search?q=hemp+bioplastic+composite+material&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=hemp+fiber+biocomposite&hl=en&gl=US&ceid=US:en",
    
    # Agriculture
    "https://news.google.com/rss/search?q=hemp+agriculture+farming+crop&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=hemp+cultivation+harvest&hl=en&gl=US&ceid=US:en",
    
    # Food & Nutrition
    "https://news.google.com/rss/search?q=hemp+seed+food+nutrition&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=hemp+protein+oil+food&hl=en&gl=US&ceid=US:en",
    
    # Automotive & Industrial
    "https://news.google.com/rss/search?q=hemp+automotive+car+industry&hl=en&gl=US&ceid=US:en",
    
    # Energy & Paper
    "https://news.google.com/rss/search?q=hemp+battery+supercapacitor+energy&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=hemp+paper+pulp+packaging&hl=en&gl=US&ceid=US:en",
    
    # Cosmetics
    "https://news.google.com/rss/search?q=hemp+cosmetics+skincare+beauty&hl=en&gl=US&ceid=US:en",
    
    # Legislation & Business
    "https://news.google.com/rss/search?q=hemp+legislation+regulation+farm+bill&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=hemp+industry+market+business&hl=en&gl=US&ceid=US:en",
    
    # Sustainability
    "https://news.google.com/rss/search?q=hemp+sustainability+eco+carbon&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=hemp+environment+green+planet&hl=en&gl=US&ceid=US:en",
    
    # === Additional hemp media ===
    "https://hemptoday.net/feed/",
    "https://www.mjbizdaily.com/hemp/feed/",

    # === Google News — by country ===

    # 🇨🇦 Canada
    "https://news.google.com/rss/search?q=hemp+canada+industry&hl=en&gl=CA&ceid=CA:en",
    "https://news.google.com/rss/search?q=hemp+farming+canada&hl=en&gl=CA&ceid=CA:en",

    # 🇬🇧 United Kingdom
    "https://news.google.com/rss/search?q=hemp+uk+industry&hl=en&gl=GB&ceid=GB:en",

    # 🇪🇺 Europe (general)
    "https://news.google.com/rss/search?q=hemp+europe+industry&hl=en&gl=GB&ceid=GB:en",
    "https://news.google.com/rss/search?q=industrial+hemp+EU+regulation&hl=en&gl=GB&ceid=GB:en",

    # 🇳🇱 Netherlands
    "https://news.google.com/rss/search?q=hemp+netherlands+industry&hl=en&gl=NL&ceid=NL:en",

    # 🇩🇪 Germany
    "https://news.google.com/rss/search?q=Hanf+Industrie+Deutschland&hl=de&gl=DE&ceid=DE:de",
    "https://news.google.com/rss/search?q=hemp+germany+industry&hl=en&gl=DE&ceid=DE:en",

    # 🇫🇷 France
    "https://news.google.com/rss/search?q=chanvre+industriel+france&hl=fr&gl=FR&ceid=FR:fr",

    # 🇮🇹 Italy
    "https://news.google.com/rss/search?q=canapa+industriale+italia&hl=it&gl=IT&ceid=IT:it",

    # 🇨🇿 Czech Republic
    "https://news.google.com/rss/search?q=konop%C3%AD+pr%C5%AFmyslov%C3%A9&hl=cs&gl=CZ&ceid=CZ:cs",
    "https://news.google.com/rss/search?q=hemp+czech+republic&hl=en&gl=CZ&ceid=CZ:en",

    # 🇵🇱 Poland
    "https://news.google.com/rss/search?q=konopie+przemys%C5%82owe+polska&hl=pl&gl=PL&ceid=PL:pl",

    # 🇺🇦 Ukraine
    "https://news.google.com/rss/search?q=hemp+ukraine+конопля&hl=uk&gl=UA&ceid=UA:uk",
    "https://news.google.com/rss/search?q=промислові+коноплі+Україна&hl=uk&gl=UA&ceid=UA:uk",

    # 🇨🇳 China
    "https://news.google.com/rss/search?q=hemp+china+industry&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=china+hemp+textile+production&hl=en&gl=US&ceid=US:en",

    # 🇮🇳 India
    "https://news.google.com/rss/search?q=hemp+india+industry&hl=en&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=hemp+india+textile+agriculture&hl=en&gl=IN&ceid=IN:en",

    # 🇦🇺 Australia
    "https://news.google.com/rss/search?q=hemp+australia+industry&hl=en&gl=AU&ceid=AU:en",

    # 🇯🇵 Japan
    "https://news.google.com/rss/search?q=hemp+industry+japan&hl=en&gl=JP&ceid=JP:en",

    # 🇰🇷 South Korea
    "https://news.google.com/rss/search?q=hemp+industry+korea&hl=en&gl=KR&ceid=KR:en",

    # 🇧🇷 Brazil
    "https://news.google.com/rss/search?q=c%C3%A2nhamo+industrial+brasil&hl=pt&gl=BR&ceid=BR:pt",

    # === Additional thematic queries (global) ===
    "https://news.google.com/rss/search?q=hemp+startup+investment+funding&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=hemp+legislation+law+2025+2026&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=hemp+bioplastic+automotive+composite&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=hemp+battery+graphene+supercapacitor&hl=en&gl=US&ceid=US:en",
]

# Ukrainian-only RSS feeds (subset for --ua-only mode)
UA_RSS_FEEDS = [
    # === Google News UA — конопляні запити ===
    "https://news.google.com/rss/search?q=%D0%BA%D0%BE%D0%BD%D0%BE%D0%BF%D0%BB%D1%96&hl=uk&gl=UA&ceid=UA:uk",
    "https://news.google.com/rss/search?q=%D0%BA%D0%BE%D0%BD%D0%BE%D0%BF%D0%BB%D1%8F%D0%BD%D0%B8%D0%B9&hl=uk&gl=UA&ceid=UA:uk",
    "https://news.google.com/rss/search?q=%D0%BF%D1%80%D0%BE%D0%BC%D0%B8%D1%81%D0%BB%D0%BE%D0%B2%D1%96+%D0%BA%D0%BE%D0%BD%D0%BE%D0%BF%D0%BB%D1%96+%D0%A3%D0%BA%D1%80%D0%B0%D1%97%D0%BD%D0%B0&hl=uk&gl=UA&ceid=UA:uk",
    "https://news.google.com/rss/search?q=hemp+ukraine&hl=uk&gl=UA&ceid=UA:uk",
    "https://news.google.com/rss/search?q=%D0%BA%D0%BE%D0%BD%D0%BE%D0%BF%D0%BB%D1%8F%D0%BD%D0%B8%D0%B9+%D0%B1%D0%B5%D1%82%D0%BE%D0%BD&hl=uk&gl=UA&ceid=UA:uk",
    "https://news.google.com/rss/search?q=%D1%82%D0%B5%D1%85%D0%BD%D1%96%D1%87%D0%BD%D1%96+%D0%BA%D0%BE%D0%BD%D0%BE%D0%BF%D0%BB%D1%96&hl=uk&gl=UA&ceid=UA:uk",

    # === Existing Ukraine feeds from RSS_FEEDS ===
    "https://news.google.com/rss/search?q=hemp+ukraine+конопля&hl=uk&gl=UA&ceid=UA:uk",
    "https://news.google.com/rss/search?q=промислові+коноплі+Україна&hl=uk&gl=UA&ceid=UA:uk",

    # === Українські агро-портали (RSS feeds) ===
    "https://agrotimes.ua/feed/",
    "https://latifundist.com/feed",
    "https://agroportal.ua/rss",
    "https://superagronom.com/rss",
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
