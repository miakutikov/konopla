# SYSTEM_MAP.md — Admin Panel Architecture Reference

> **Last updated:** 2026-03-28 (Задача 7 — migration + cleanup)
> **Main file:** `layouts/admin/list.html` (7395 lines)
> **Structure:** Single-file SPA — HTML (1-599) | CSS (600-2933) | JS (2935-7394)

---

## File Structure

```
layouts/admin/list.html     — 7395 lines, main admin SPA
layouts/admin/catalog/      — redirect to /admin/#catalog
scripts/main.py             — pipeline entry (discover/process)
scripts/fetcher.py          — RSS fetching + filtering
scripts/rewriter.py         — Gemini AI rewriting
scripts/config.py           — keywords, prompts, constants
scripts/relevance.py        — relevance scoring (compute_relevance, guess_category)
scripts/publisher.py        — Hugo .md file creation
scripts/migrate_drafts.py   — one-time drafts.json → workflow.json migration
scripts/scheduler.py        — scheduled post executor
scripts/telegram_bot.py     — Telegram notifications
scripts/images.py           — image sourcing (original/Gemini/Unsplash)
data/candidates.json        — raw RSS candidates
data/drafts.json            — LEGACY (no longer written by pipeline, kept for admin read-only)
data/workflow.json           — unified workflow state {"articles": [...]}
data/sources.json           — RSS sources (90+)
data/catalog.json           — company directory
data/scheduled.json         — scheduled posts
data/social_status.json     — social posting history
data/pinned.json            — pinned homepage article
data/feed_health.json       — feed success/failure stats
data/processed.json         — MD5 hashes of processed articles
```

---

## Sidebar → Views → Line Ranges

| Sidebar Label | data-view | HTML ID | CSS (key classes) |
|---------------|-----------|---------|-------------------|
| 📡 Стрічка | feed | view-feed | `.candidates-*`, `.candidate-card`, `.relevance-stars`, `.trust-badge`, `.category-hint`, `.candidate-preview`, `.candidate-shortlist-btn` |
| ✍️ Редакція | editorial | view-editorial | `.editorial-*`, `.wf-card`, `.wf-status-*`, `.drafts-*`, `.draft-card`, `.create-form` |
| 🚀 Публікація | publishing | view-publishing | `.pub-channels`, `.pub-channel`, `.pub-channel-header`, `.pub-channel-actions`, `.pub-channel-empty`, `.queue-items`, `.scheduled-items` |
| 📚 Архів | archive | view-archive | `.articles-*`, `.article-row`, `.channel-badge`, `.ch-done`, `.ch-pending`, `.ch-scheduled`, `.articles-stats`, `.repost-btn` |
| 📊 Аналітика | analytics | view-analytics | `.stats-*`, `.chart-*`, `.calendar-*`, `.cal-*` |
| ⚙️ Налаштування | settings | view-settings | `.sources-*`, `.source-*`, `.yt-*` |
| 📋 Каталог | catalog | view-catalog | `.cat-*`, `.company-form-*` |

**Aliases (backwards compat):** `candidates→feed`, `moderation→editorial`, `articles→archive`

**Editorial sub-sections:**
- Workflow tabs (queued/drafts/all) with `.editorial-tabs`
- Workflow cards with `.wf-card`, `.wf-status-badge`
- Create Form (`.create-form`, `.cf-*`)
- Drafts List (legacy, hidden in "Чернетки" tab)

**Publishing sub-sections:**
- 3 channel cards: `pub-website`, `pub-telegram`, `pub-threads`
- Each has: header + action buttons, queue-items, scheduled-items, empty state
- Queues loaded from localStorage in `showPanel()`, no lazy loading needed

---

## Global Variables (JS)

| Line | Variable | Type | Purpose |
|------|----------|------|---------|
| 2939 | `ADMIN_KEY_HASH` | string | Admin password hash (from Hugo config) |
| 2940 | `GITHUB_REPO` | string | Repo path (from Hugo config) |
| 2941 | `SITE_URL` | string | Base URL (from Hugo config) |
| 2943 | `ghToken` | string | GitHub PAT (from localStorage) |
| 2944 | `adminKey` | string | Admin password |
| 2945 | `approvedQueue` | array | Deploy queue (localStorage) |
| 2946 | `telegramQueue` | array | Telegram queue (localStorage) |
| 2947 | `threadsQueue` | array | Threads queue (localStorage) |
| 2948 | `editingFile` | object/null | Article being edited |
| 2949 | `SOCIAL_STATUS` | object | Social posting status cache |
| 3239 | `workflowData` | array | Workflow articles from workflow.json |
| 3240 | `workflowSha` | string | workflow.json GitHub SHA |
| 3241 | `editorialTab` | string | Active editorial sub-tab (queued/drafts/all) |
| 2951 | `ALL_ARTICLES` | array | All articles (Hugo template-generated) |
| 2957 | `PINNED_FILENAME` | string | Currently pinned article |
| 2959 | `AUTOFORMAT_PROMPT` | string | Gemini AI prompt for formatting |
| 3014 | `currentView` | string | Active sidebar tab |
| 3015 | `chartsInitialized` | bool | Analytics lazy-load flag |
| 3016 | `catalogLoaded` | bool | Catalog lazy-load flag |
| 3017 | `catalogData` | object/null | Catalog JSON |
| 3018 | `catalogSha` | string | Catalog.json GitHub SHA |
| 3019 | `catalogEditingId` | string | Company being edited |
| 4947 | `ARTICLES_PER_PAGE` | number | Pagination size (20) |
| 4948 | `articlesPage` | number | Current page |
| 4569 | `quillEditor` | object | Quill WYSIWYG instance |
| 4570 | `turndownService` | object | HTML→MD converter |
| 5459 | `candidatesData` | array | Candidates array |
| 5460 | `candidatesSelected` | object | Selection state {id: bool} |
| 5461 | `candidatesSha` | string | candidates.json SHA |
| 5754 | `sourcesData` | array | Sources array |
| 5755 | `sourcesSha` | string | sources.json SHA |
| 5756 | `editingSourceIdx` | number | Source being edited |

---

## JS Functions by Module

### Auth & Navigation
| Line | Function | Description |
|------|----------|-------------|
| 2986 | `init()` | Entry point: check auth |
| 3005 | `showAuth()` | Show login screen |
| 3021 | `showView(name)` | Switch active tab |
| 3074 | `updateBadges()` | Update sidebar badge counts |
| 3089 | `toggleMobileSidebar()` | Mobile menu toggle |
| 3094 | `toggleSidebarCollapse()` | Desktop sidebar collapse |
| 3109 | `showPanel()` | Show admin after auth, load data |
| 3151 | `checkAuth(key)` | Verify password hash |
| 3168 | `logout()` | Clear session, show login |
| 3176 | `sha256(str)` | SHA-256 hash |

### Moderation & Drafts (Legacy)
| Line | Function | Description |
|------|----------|-------------|
| 3193 | `showPatSetup()` | GitHub PAT setup form |
| 3205 | `saveToken()` | Save PAT to localStorage |
| 3218 | `loadDrafts()` | Fetch drafts.json, render cards |
| 3310 | `approveArticle(filename, id)` | Approve: draft→published + add to ALL queues |
| 3395 | `deleteArticle(filename, id)` | Delete draft |
| 3445 | `deleteArticleRow(filename, id)` | Delete from articles list |
| 3483 | `runPipeline()` | Trigger pipeline.yml + ua_pipeline.yml |
| 3517 | `removeDraftEntry(id)` | Remove from drafts.json |

### Editorial (Workflow)
| Line | Function | Description |
|------|----------|-------------|
| 3848 | `loadEditorial()` | Load workflow.json + drafts.json in parallel |
| 3853 | `loadWorkflowArticles()` | Fetch workflow.json into workflowData |
| 3872 | `switchEditorialTab(tab)` | Switch queued/drafts/all sub-tab |
| 3880 | `renderEditorial()` | Render workflow cards with status badges |
| 3994 | `updateEditorialCounter()` | Update tab counters + sidebar badge |
| 4025 | `processWorkflowItem(id)` | Dispatch pipeline for single candidate → AI rewrite |
| 4057 | `processQueuedWorkflow()` | Bulk process all queued candidates |
| 4090 | `removeWorkflowItem(id)` | Remove from workflow.json |
| 4103 | `saveWorkflowData(msg)` | Save workflow.json to GitHub |

### Queues (Deploy/TG/Threads) — rendered in Publishing view
| Line | Function | Description |
|------|----------|-------------|
| 3545 | `loadQueue()` | Load deploy queue from localStorage |
| 3554 | `saveQueue()` | Save deploy queue to localStorage |
| 3558 | `renderQueue()` | Render deploy queue cards |
| 3591 | `removeFromQueue(idx)` | Remove from deploy queue |
| 3597 | `clearQueue()` | Clear deploy queue |
| 3604 | `deployAll()` | Dispatch moderate.yml |
| 3622 | `triggerDeploy()` | Dispatch moderate.yml (helper) |
| 3632 | `triggerManualDeploy()` | Manual deploy button |
| 3751 | `loadTgQueue()` | Load TG queue from localStorage |
| 3760 | `saveTgQueue()` | Save TG queue |
| 3764 | `renderTgQueue()` | Render TG queue |
| 3797 | `removeFromTgQueue(idx)` | Remove from TG queue |
| 3803 | `clearTgQueue()` | Clear TG queue |
| 3810 | `postToTelegram()` | Write telegram_queue.json + dispatch workflow |
| 3864 | `loadThreadsQueue()` | Load Threads queue |
| 3873 | `saveThreadsQueue()` | Save Threads queue |
| 3877 | `renderThreadsQueue()` | Render Threads queue |
| 3910 | `removeFromThreadsQueue(idx)` | Remove from Threads queue |
| 3916 | `clearThreadsQueue()` | Clear Threads queue |
| 3923 | `postToThreads()` | Write threads_queue.json + dispatch workflow |
| 3978 | `setSchedulePreset(type, idx, hour)` | Set schedule to 08/14/20 Kyiv |
| 4008 | `scheduleArticle(type, idx)` | Schedule post to scheduled.json |
| 4091 | `cancelScheduled(type, itemId)` | Cancel scheduled post |
| 4123 | `loadScheduledItems()` | Fetch scheduled.json |
| 4139 | `renderScheduledSection(type, items)` | Render scheduled items per queue |

### Article Editor
| Line | Function | Description |
|------|----------|-------------|
| 4540 | `resetCreateForm()` | Clear create form |
| 4569-70 | `quillEditor / turndownService` | Editor instances |
| 4572 | `initQuill()` | Initialize Quill WYSIWYG |
| 4624 | `toggleCreateForm()` | Show/hide create form |
| 4641 | `slugifyUA(text)` | Ukrainian text → URL slug |
| 4666 | `createArticle()` | Save new/edited article to GitHub |
| 4797 | `editArticle(filename)` | Load article for editing |
| 4855 | `autoFormat()` | Gemini AI auto-format |
| 5171 | `generateImage()` | AI image generation |

### Image Handling
| Line | Function | Description |
|------|----------|-------------|
| 3647 | `updateImagePreview()` | Preview image from URL |
| 3671 | `clearImage()` | Clear image preview |
| 3676 | `openImageLightbox()` | Lightbox modal |
| 3684 | `closeImageLightbox()` | Close lightbox |
| 3688 | `uploadImage(fileInput)` | Upload image to GitHub |

### YouTube
| Line | Function | Description |
|------|----------|-------------|
| 4189 | `toggleYtPanel()` | Show YouTube search |
| 4203 | `ytPanelSearch()` | Search YouTube API |
| 4272 | `addYtVideo(id, mode)` | Add video as article |

### Articles List (Archive)
| Line | Function | Description |
|------|----------|-------------|
| ~5642 | `getArticleChannels(a)` | Get 3-channel statuses (website/TG/Threads) from SOCIAL_STATUS + workflow.json |
| ~5614 | `renderArticles()` | Render all articles with filters + stats bar |
| ~5635 | `articlesGoTo(page)` | Pagination |
| ~5642 | `filterArticles(reset)` | Filter by search/status/category/channel |
| ~5676 | `buildRow(a)` | Build article row with 3-channel badges + re-post buttons |
| ~5772 | `pinArticle(filename)` | Pin to homepage |
| ~5806 | `unpinArticle()` | Unpin from homepage |

### Analytics & Calendar
| Line | Function | Description |
|------|----------|-------------|
| 5271 | `renderStats()` | Render stats + charts |
| 5349 | `initCalendar()` | Init calendar |
| 5356 | `calendarPrev()` | Previous month |
| 5361 | `calendarNext()` | Next month |
| 5366 | `calendarToday()` | Current month |
| 5373 | `renderCalendar()` | Render calendar grid |
| 5427 | `showCalendarDay(dateStr)` | Show articles for day |

### Feed (Candidates)
| Line | Function | Description |
|------|----------|-------------|
| 5568 | `timeAgo(dateStr)` | Relative time formatting |
| 5576 | `toggleCandidatesTab()` | Switch to feed view |
| 5580 | `loadCandidates()` | Fetch candidates.json |
| 5623 | `renderRelevanceStars(score)` | ★★★☆☆ stars + score badge |
| 5632 | `renderCandidates()` | Render cards with relevance, sorting, badges |
| 5734 | `updateCandidatesCounter()` | Update "В роботу (N)" button text |
| 5754 | `candidateToggle(id, checked)` | Toggle checkbox |
| 5763 | `candidatesToggleAll(checked)` | Select/deselect all |
| 5787 | `filterCandidates()` | Filter by type |
| 5794 | `toggleCandidatePreview(id)` | Expand content_preview |
| 5799 | `refreshCandidates()` | Trigger discover pipeline |
| 5823 | `processCandidates()` | Process selected → pipeline.yml |
| 5853 | `deleteCandidate(id)` | Delete single candidate |
| 5876 | `deleteSelectedCandidates()` | Delete selected candidates |
| 5907 | `shortlistCandidate(id)` | Move single candidate → workflow.json |
| 5914 | `shortlistSelected()` | Move selected → workflow.json (bulk) |
| 5923 | `_shortlistCandidates(arr)` | Internal: write workflow + remove candidates |

### Sources (Settings)
| Line | Function | Description |
|------|----------|-------------|
| 5758 | `toggleSourcesTab()` | Switch to sources |
| 5762 | `loadSources()` | Fetch sources.json |
| 5796 | `renderSources()` | Render sources list |
| 5843 | `filterSources()` | Filter by region/status |
| 5847 | `toggleSourceAddForm()` | Toggle source form |
| 5863 | `cancelSourceForm()` | Close source form |
| 5868 | `editSource(idx)` | Edit source |
| 5881 | `saveSource()` | Save source to GitHub |
| 5940 | `toggleSourceActive(idx)` | Toggle source on/off |

### Social (Telegram/Threads Modal)
| Line | Function | Description |
|------|----------|-------------|
| 5989 | `loadSocialStatus()` | Fetch social_status.json |
| 6001 | `openSocialModal(filename, platform)` | Open publish modal |
| 6068 | `closeSocialModal()` | Close modal |
| 6073 | `publishSocial()` | Dispatch social workflow |

### Catalog
| Line | Function | Description |
|------|----------|-------------|
| 6138 | `catSlugify(text)` | Slug for catalog |
| 6143 | `loadCatalog()` | Fetch catalog.json |
| 6161 | `saveCatalogData(msg)` | Save catalog to GitHub |
| 6181 | `populateCatalogSelects()` | Populate dropdowns |
| 6203 | `renderCompanies()` | Render companies table |
| 6264 | `showCompanyForm(id)` | Open company form |
| 6312 | `hideCompanyForm()` | Close company form |
| 6317 | `editCompany(id)` | Edit company |
| 6319 | `autoSlug()` | Auto-generate slug |
| 6325 | `updateCatalogLogoPreview(url)` | Logo preview |
| 6341 | `uploadCatalogLogo(input)` | Upload logo |
| 6370 | `saveCompany()` | Save company |
| 6460 | `deleteCompany(id, name)` | Delete company |
| 6468 | `triggerCatalogDeploy()` | Deploy catalog changes |

### Utility
| Line | Function | Description |
|------|----------|-------------|
| 4390 | `b64DecodeUtf8(b64)` | Base64 → UTF-8 |
| 4399 | `b64EncodeUtf8(str)` | UTF-8 → Base64 |
| 4408 | `ghApi(method, path, body)` | GitHub API wrapper |
| 4437 | `showStatus(msg, type)` | Status bar message |
| 4456 | `escHtml(str)` | HTML escape |
| 4461 | `disableCard(card)` | Dim card during operation |
| 4467 | `enableCard(card)` | Re-enable card |
| 4477 | `parseFrontmatter(raw)` | Parse YAML frontmatter |
| 4508 | `markdownToHtml(md)` | MD → HTML |
| 5463 | `timeAgo(dateStr)` | Relative time format |

---

## localStorage Keys

| Key | Purpose |
|-----|---------|
| `konopla_admin_key` | Hashed admin password |
| `konopla_admin_view` | Last active view |
| `konopla_sidebar_collapsed` | Sidebar state |
| `konopla_gh_token` | GitHub PAT |
| `konopla_deploy_queue` | Deploy queue JSON |
| `konopla_tg_queue` | Telegram queue JSON |
| `konopla_threads_queue` | Threads queue JSON |
| `konopla_yt_key` | YouTube API key |
| `konopla_gemini_key` | Gemini API key |

---

## GitHub Workflows

| Workflow | Triggered By | Purpose |
|----------|-------------|---------|
| `pipeline.yml` | `refreshCandidates()`, `processCandidates()`, `runPipeline()` | RSS discover + AI process |
| `ua_pipeline.yml` | `runPipeline()` | Ukraine-specific discovery |
| `moderate.yml` | `deployAll()`, `triggerDeploy()`, `triggerManualDeploy()`, `triggerCatalogDeploy()` | Hugo build + deploy |
| `telegram_post.yml` | `postToTelegram()`, `publishSocial()` | Post to Telegram |
| `threads_post.yml` | `postToThreads()`, `publishSocial()` | Post to Threads |

---

## Data Flow

```
RSS Sources (sources.json, 90+ feeds)
  ↓ [pipeline.yml action=discover, every 6h]
  ↓ fetcher.py → filter by keywords/drugs/age/dedup
  ↓
candidates.json (raw items + relevance_score + category_hint, max 200, 7-day TTL)
  ↓ [admin: "Обробити вибрані" → pipeline.yml action=process]
  ↓ rewriter.py → Gemini translate to Ukrainian
  ↓ images.py → find/generate image
  ↓ publisher.py → create .md file with draft:true
  ↓
content/news/*.md (draft:true) + drafts.json + workflow.json (stage=editorial)
  ↓ [admin: approveArticle() → draft:false]
  ↓ [AUTO-adds to deploy + TG + Threads queues (localStorage)]
  ↓
Deploy Queue → moderate.yml → Hugo build → GitHub Pages
TG Queue → telegram_post.yml → Telegram channel
Threads Queue → threads_post.yml → Threads profile
  ↓
Published article on konopla.ua + social posts
  ↓
social_status.json (tracking)
```

---

## Pipeline Config (scripts/config.py)

| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_ARTICLES_PER_RUN` | 15 | Max articles per discover |
| `MAX_AGE_DAYS` | 5 | Article age filter |
| `MIN_TITLE_LENGTH` | 20 | Title length filter |
| `SIMILARITY_THRESHOLD` | 0.6 | Dedup threshold |
| `API_DELAY_SECONDS` | 5 | Delay between Gemini calls |
| `CANDIDATES_MAX_AGE_DAYS` | 7 | Candidate TTL |
| `CANDIDATES_MAX_ITEMS` | 200 | Max candidates |

---

## Categories

`текстиль` | `будівництво` | `агро` | `біопластик` | `автопром` | `харчова` | `енергетика` | `косметика` | `законодавство` | `наука` | `екологія` | `бізнес` | `відео` | `інше`
