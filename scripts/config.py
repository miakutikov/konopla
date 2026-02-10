# === KONOPLA.UA Configuration ===

import os

# RSS feeds — industrial hemp news sources
RSS_FEEDS = [
    # === Dedicated hemp industry media ===
    "https://hempindustrydaily.com/feed/",
    "https://www.hemptodaymag.com/feed/",
    "https://hempbuildermag.com/feed/",
    "https://www.forbes.com/hemp/feed/",
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
    
    # === European sources (important for UA context) ===
    "https://news.google.com/rss/search?q=hemp+europe+industry&hl=en&gl=GB&ceid=GB:en",
    "https://news.google.com/rss/search?q=hemp+ukraine+конопля&hl=uk&gl=UA&ceid=UA:uk",
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
- Текст: 150-300 слів, 3-5 абзаців
- Перший абзац: головна новина (хто, що, де, коли)
- Далі: деталі і контекст
- Останній абзац: чому це важливо / що це означає для індустрії

## Обмеження
- НІКОЛИ не згадуй наркотичне використання, марихуану, рекреаційний канабіс
- THC можна згадувати ТІЛЬКИ в контексті законодавчих лімітів (наприклад "вміст ТГК до 0.3%")
- Не вигадуй факти яких немає в оригіналі
- Не додавай свою думку

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
  "image_query": "2-3 англійських слова для пошуку фото на Unsplash (наприклад: hemp textile factory)"
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

# File to track already processed articles (prevents duplicates)
PROCESSED_FILE = "data/processed.json"

# Delay between Gemini API calls (seconds) to stay within free tier
API_DELAY_SECONDS = 5

# Delay between Telegram messages (seconds)
TELEGRAM_DELAY_SECONDS = 3
