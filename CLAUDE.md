# KONOPLA.UA — Нотатки для Claude

## Інфраструктура

- **Google Search Console** — підключена ✓ (верифіковано ~8 бер. 2026)
- **Sitemap** — подано: `https://konopla.ua/sitemap.xml` (останнє читання: 13 бер. 2026) ✓
- **Google Analytics** — шаблон готовий (`layouts/partials/analytics.html`), але GA4 Measurement ID ще не вставлено в `hugo.toml`
- **Bing Webmaster Tools** — не підключено

## Гілки

- Робоча гілка: `claude/deploy-admin-session-fix-ikMS8`

## Архітектура

- **Hugo** — статичний сайт, деплой на GitHub Pages
- **Pipeline** — один воркфлоу `.github/workflows/pipeline.yml`, запускається кожні 6 год або вручну з вибором `region: all | global | ua`
- **Джерела новин** — `data/sources.json` (62 джерела), легко доповнювати
- **Модерація** — статті публікуються як `draft: true`, схвалення через `/admin/`
