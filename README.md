# 🌿 Konopla.UA — Портал промислових конопель

Автономна система збору, рерайту та публікації новин + база знань + каталог компаній конопляної галузі.

---

## 🗂 Структура сайту

| Розділ | URL | Опис |
|---|---|---|
| Головна | `/` | Стрічка свіжих новин |
| Новини | `/news/` | Всі новини з тегами |
| База знань | `/knowledge/` | Статті-посібники |
| Каталог | `/catalog/` | Компанії галузі |
| Про нас | `/about/` | Інформація |
| Пошук | `/search/` | Пошук по сайту |
| Адмін | `/admin/` | Модерація новин |
| Адмін каталогу | `/admin/catalog/` | Управління компаніями |

---

## 🚀 Розгортання

### Крок 1 — GitHub репозиторій

1. github.com → **"+"** → **"New repository"**
2. Назва: `konopla`
3. Тип: **Public**
4. **"Create repository"**

```bash
git init && git add . && git commit -m "Init"
git remote add origin https://github.com/USERNAME/konopla.git
git push -u origin main
```

### Крок 2 — Секрети

Settings → Secrets and variables → Actions → New repository secret:

| Secret | Що це | Де взяти | Обов'язковий |
|---|---|---|---|
| `GEMINI_API_KEY` | Gemini AI для рерайту | aistudio.google.dev | ✅ Або OPENROUTER |
| `OPENROUTER_API_KEY` | OpenRouter AI (альтернатива) | openrouter.ai | ✅ Або GEMINI |
| `TELEGRAM_TOKEN` | Токен Telegram-бота | @BotFather → /newbot | ✅ |
| `TELEGRAM_CHAT_ID` | ID каналу новин | @your_channel або число | ✅ |
| `ADMIN_CHAT_ID` | ID чату для алертів | особистий chat ID | Ні |
| `UNSPLASH_ACCESS_KEY` | Фото для статей | unsplash.com/developers | Ні |
| `YOUTUBE_API_KEY` | Моніторинг YouTube | console.cloud.google.com | Ні |
| `THREADS_USER_ID` | ID акаунту Threads | Meta API | Ні |
| `THREADS_ACCESS_TOKEN` | Токен Threads | Meta API | Ні |

> **AI:** достатньо одного з двох — Gemini (безкоштовний) або OpenRouter (платний, кращий рерайт).

### Крок 3 — GitHub Pages

Settings → Pages → Source: **"GitHub Actions"** → Save

### Крок 4 — Перший запуск

Actions → "KONOPLA.UA News Pipeline" → **"Run workflow"** → вибери `all`

### Крок 5 — Домен konopla.ua

Settings → Pages → Custom domain: `konopla.ua`

DNS записи у реєстратора:
```
CNAME  www   → USERNAME.github.io
A      @     → 185.199.108.153
A      @     → 185.199.109.153
A      @     → 185.199.110.153
A      @     → 185.199.111.153
```

Зачекай 10-30 хв → Settings → Pages → ✅ Enforce HTTPS

---

## 🔧 Керування

### Розклад pipeline
Файл `.github/workflows/pipeline.yml`, параметр `cron`:
- `0 */6 * * *` — кожні 6 годин (за замовчуванням)
- `0 */3 * * *` — кожні 3 години
- `0 8,14,20 * * *` — о 8:00, 14:00, 20:00

Або ручний запуск: Actions → KONOPLA.UA News Pipeline → Run workflow (вибір: `all` / `global` / `ua`)

### Додати RSS джерело
`scripts/config.py` → масив `RSS_FEEDS` → додай URL

### Видалити новину
Видали файл з `content/news/` → commit → сайт перебудується

### Стоп-слова
`scripts/config.py` → `STOP_WORDS` (жорсткі) або `SOFT_STOP_WORDS` (контекстні)

### Каталог компаній
Керується через `/admin/catalog/` — захищено паролем. Дані зберігаються в `data/catalog.json`.

---

## 📋 Модерація

Система підтримує режим чернеток: нові статті спочатку потрапляють у `data/drafts.json`, де їх можна переглянути і схвалити через адмін-панель (`/admin/`) перед публікацією.

---

## 🔍 Моніторинг

Автоматичні алерти в Telegram:

| Ситуація | Рівень | Повідомлення |
|---|---|---|
| Нових новин не знайдено | ℹ️ INFO | Тихе, без звуку |
| Більше помилок ніж успіхів | ⚠️ WARN | Зі звуком |
| Всі статті зафейлились | ❌ ERROR | Зі звуком |
| Pipeline впав | 🚨 CRITICAL | Зі звуком |

Алерти йдуть у `ADMIN_CHAT_ID` (якщо заданий) або в канал новин.

---

## 📁 Структура проєкту

```
konopla/
├── .github/workflows/pipeline.yml   ← Розклад + деплой
├── hugo.toml                        ← Конфігурація сайту
├── CLAUDE.md                        ← Інструкції для AI асистента
├── content/
│   ├── about.md                     ← Сторінка "Про нас"
│   ├── news/                        ← Новини (автоматично)
│   ├── knowledge/                   ← База знань (статті)
│   └── catalog/                     ← Сторінки компаній
├── data/
│   ├── processed.json               ← Трекер дублікатів
│   ├── drafts.json                  ← Чернетки (модерація)
│   ├── catalog.json                 ← База компаній каталогу
│   └── sources.json                 ← Налаштування джерел RSS
├── layouts/
│   ├── _default/                    ← Базові шаблони
│   ├── index.html                   ← Головна
│   ├── news/                        ← Шаблони новин
│   ├── catalog/                     ← Шаблони каталогу
│   ├── knowledge/                   ← Шаблони бази знань
│   ├── admin/                       ← Адмін-панель новин
│   │   └── catalog/                 ← Адмін-панель каталогу
│   └── partials/
│       ├── seo-head.html            ← SEO, OG, JSON-LD
│       ├── header.html              ← Шапка + навігація
│       ├── footer.html              ← Підвал
│       └── article-card.html        ← Картка новини
├── scripts/
│   ├── config.py                    ← Всі налаштування
│   ├── fetcher.py                   ← Збір RSS
│   ├── rewriter.py                  ← AI рерайт (Gemini / OpenRouter)
│   ├── publisher.py                 ← Генерація markdown
│   ├── moderator.py                 ← Управління чернетками
│   ├── images.py                    ← Unsplash / AI фото
│   ├── telegram_bot.py              ← Постинг у Telegram
│   ├── telegram_poster.py           ← Розширений Telegram постинг
│   ├── threads_poster.py            ← Постинг у Threads
│   ├── youtube_monitor.py           ← Моніторинг YouTube каналів
│   ├── instagram.py                 ← Генерація Stories
│   ├── monitor.py                   ← Алерти та моніторинг
│   ├── scheduler.py                 ← Планувальник завдань
│   └── main.py                      ← Оркестратор
└── static/
    ├── css/style.css                ← Стилі (CSS змінні + темна тема)
    ├── images/
    │   └── generated/               ← AI-згенеровані зображення
    ├── favicon.svg                  ← Іконка
    ├── robots.txt                   ← SEO
    └── instagram/                   ← Згенеровані Stories
```

---

## 💰 Вартість

| Компонент | Ціна |
|---|---|
| GitHub Pages | $0 |
| GitHub Actions | $0 (2000 хв/міс) |
| Gemini API | $0 (free tier) |
| OpenRouter API | від $0.001/запит (опційно) |
| Unsplash API | $0 (50 req/hr) |
| Домен konopla.ua | ~$10/рік |
| **Разом** | **~$10/рік** |

---

## ❓ FAQ

**Pipeline не запускається**
→ Перевір Actions → чи увімкнені workflows → чи правильні секрети

**Новини не з'являються**
→ Зачекай 6 годин або запусти вручну. Перевір логи в Actions.

**Сайт не відкривається**
→ Перевір DNS записи. Зачекай до 30 хвилин після зміни.

**Telegram не постить**
→ Перевір: бот доданий адміністратором каналу? TELEGRAM_CHAT_ID правильний?

**Як змінити дизайн?**
→ Редагуй `static/css/style.css`. Кольори задані через CSS змінні на початку файлу.

**Скільки новин на день?**
→ В середньому 8-16 новин (2-4 за кожен запуск, 4 запуски на день).

**Gemini перестав працювати**
→ Можливо перевищено ліміт (15 req/min). Як альтернатива — підключи `OPENROUTER_API_KEY`.

**Як додати компанію до каталогу?**
→ Зайди на `/admin/catalog/`, авторизуйся паролем, натисни "+ Додати компанію".
