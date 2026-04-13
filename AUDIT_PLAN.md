# KONOPLA.UA Admin Portal — Code Audit Plan
> Standard: Apple Engineering Quality. Every function reviewed, tested, optimized.
> Rule: **one function per session**. No shortcuts. No skipping.

---

## Методологія перевірки (Review Standards)

Кожна функція проходить **8-точковий чеклист**:

```
[ ] 1. CORRECTNESS    — чи функція робить те, що обіцяє? edge cases?
[ ] 2. ERROR HANDLING — чи всі помилки відловлені і показані юзеру (не тільки console)?
[ ] 3. RACE CONDITIONS — чи є stale SHA / double-click / concurrent calls?
[ ] 4. PERFORMANCE    — зайві API calls? можна кешувати? зайвий re-render?
[ ] 5. UX             — loading states? disable кнопок під час виконання? feedback?
[ ] 6. SECURITY       — XSS? витік токену? dangerouslySetInnerHTML-еквіваленти?
[ ] 7. CODE CLARITY   — читабельність, назви змінних, коментарі
[ ] 8. DEAD CODE      — чи є невикористані змінні/гілки/fallbacks?
```

**Результат кожної сесії:**
- Оцінка: 🔴 Critical / 🟡 Needs work / 🟢 OK
- Конкретні зміни або підтвердження що все добре
- Оновлений код або "no changes needed"

---

## Пріоритети (P0 → P3)

| Пріоритет | Критерій |
|-----------|----------|
| **P0 — Blocking** | Функція ламає дані / безпека / core workflow |
| **P1 — High** | Щодня використовується, UX критичний |
| **P2 — Medium** | Регулярне використання, але не блокуючий |
| **P3 — Low** | Рідко, допоміжне, nice-to-have |

---

## ФАЗА 1 — Core Infrastructure (sessions 1–9)
> Все інше залежить від цих функцій. Починаємо тут.

| # | Пріоритет | Функція | Лінія | Причина |
|---|-----------|---------|-------|---------|
| 1 | P0 | `ghApi(method, path, body)` | 6227 | Всі GitHub операції через неї. Retry logic, error handling, rate limits |
| 2 | P0 | `b64DecodeUtf8(b64)` | 6209 | Cyrillic corruption якщо зламана |
| 3 | P0 | `b64EncodeUtf8(str)` | 6218 | Пара до decode, всі PUT операції |
| 4 | P0 | `parseFrontmatter(raw)` | 6296 | Парсить кожну статтю — баг тут = порчений контент |
| 5 | P1 | `showStatus(msg, type)` | 6256 | Єдиний feedback-канал до юзера |
| 6 | P1 | `checkAuth(key)` | 4351 | Auth flow, sha256, localStorage |
| 7 | P1 | `init()` | 4172 | Bootstrap: URL params, localStorage, token check |
| 8 | P1 | `showView(name)` | 4210 | Навігація між всіма вкладками |
| 9 | P1 | `updateBadges()` | 4271 | Лічильники по всьому порталу |

---

## ФАЗА 2 — Feed / Candidates (sessions 10–26)
> Щодня: pipeline → candidates → shortlist/delete. Критичний шлях.

| # | Пріоритет | Функція | Лінія | Фокус аудиту |
|---|-----------|---------|-------|--------------|
| 10 | P0 | `loadCandidates()` | 7362 | Orchestration: fetch + append YouTube + render |
| 11 | P0 | `appendYouTubeDraftsToCandidates()` | 7412 | Synthetic створення — щойно фіксили, треба ретельно |
| 12 | P0 | `addToProcessed(candidates)` | 7701 | processed.json integrity — pipeline dedup залежить |
| 13 | P0 | `deleteCandidate(id)` | 7735 | Single delete — synthetic vs real branching |
| 14 | P0 | `deleteSelectedCandidates()` | 7822 | Batch delete — щойно рефакторили |
| 15 | P0 | `deleteDraftArticleByFilename(fn)` | 7787 | PUT integrity, error propagation |
| 16 | P0 | `_shortlistCandidates(arr)` | 7909 | workflow.json write + SHA update |
| 17 | P1 | `renderCandidates()` | 7479 | Render logic, filters, XSS-risk в innerHTML |
| 18 | P1 | `shortlistCandidate(id)` | 7893 | Single shortlist UX |
| 19 | P1 | `shortlistSelected()` | 7900 | Batch shortlist UX |
| 20 | P1 | `processCandidates()` | 7670 | Pipeline trigger |
| 21 | P1 | `refreshCandidates()` | 7646 | Re-fetch UX, loading state |
| 22 | P2 | `updateCandidatesCounter()` | 7581 | Badge accuracy |
| 23 | P2 | `candidateToggle(id, checked)` | 7601 | Checkbox state management |
| 24 | P2 | `candidatesToggleAll(checked)` | 7610 | Select-all edge cases |
| 25 | P2 | `filterCandidates()` | 7634 | Filter correctness |
| 26 | P2 | `toggleCandidatePreview(id)` | 7641 | DOM manipulation |

---

## ФАЗА 3 — Editorial / Workflow (sessions 27–42)
> Серце редакційного процесу.

| # | Пріоритет | Функція | Лінія | Фокус аудиту |
|---|-----------|---------|-------|--------------|
| 27 | P0 | `saveWorkflowData(message)` | 5364 | SHA management, atomic write |
| 28 | P0 | `loadWorkflowArticles()` | 4887 | Base завантаження workflowData |
| 29 | P0 | `loadEditorial()` | 4882 | Orchestration load + render |
| 30 | P1 | `renderEditorial()` | 4914 | Render logic, status cards |
| 31 | P1 | `processWorkflowItem(id)` | 5099 | Pipeline dispatch для одного item |
| 32 | P1 | `processQueuedWorkflow()` | 5131 | Batch pipeline dispatch |
| 33 | P1 | `removeWorkflowItem(id)` | 5352 | Delete з workflow + confirmation |
| 34 | P1 | `_removeFromWorkflow(id)` | 5165 | Internal delete (без confirm) |
| 35 | P1 | `quickAddUrl()` | 5212 | Add URL: YouTube detection + draft create |
| 36 | P1 | `retryProcessing(id)` | 5339 | Retry failed items |
| 37 | P2 | `switchEditorialTab(tab)` | 4906 | Tab filter UX |
| 38 | P2 | `updateEditorialCounter()` | 5062 | Badge count |
| 39 | P2 | `toggleQuickAdd()` | 5173 | Form toggle |
| 40 | P2 | `_tryResolveGoogleNewsUrl(url)` | 5185 | URL resolution logic |
| 41 | P2 | `resolveGoogleNewsInCard(id)` | 5197 | UX wrapper |
| 42 | P2 | `saveArticleUrl(id)` | 5324 | In-card URL edit save |

---

## ФАЗА 4 — Drafts & Article Management (sessions 43–52)
> Робота зі статтями: create, edit, approve, delete.

| # | Пріоритет | Функція | Лінія | Фокус аудиту |
|---|-----------|---------|-------|--------------|
| 43 | P0 | `approveArticle(filename, id)` | 4511 | drafts → workflow, date update, SHA chain |
| 44 | P0 | `deleteArticle(filename, id)` | 4617 | Delete from GitHub + drafts.json |
| 45 | P0 | `createArticle()` | 6485 | Form validation, frontmatter build, PUT |
| 46 | P0 | `editArticle(filename)` | 6616 | Load + parse frontmatter, Quill init |
| 47 | P1 | `loadDrafts()` | 4418 | drafts.json завантаження |
| 48 | P1 | `renderArticles()` | 6769 | Archive render, pagination, filters |
| 49 | P1 | `filterArticles(resetPage)` | 6828 | Filter logic |
| 50 | P1 | `autoFormat()` | 6674 | Gemini API call, error handling |
| 51 | P2 | `toggleCreateForm()` | 6443 | Form show/hide, state reset |
| 52 | P2 | `resetCreateForm()` | 6359 | Form clear |
| 53 | P2 | `initQuill()` | 6391 | Rich text editor init |
| 54 | P2 | `generateImage()` | 7058 | Gemini Vision integration |
| 55 | P2 | `uploadImage(fileInput)` | 5515 | Image upload to GitHub |
| 56 | P2 | `pinArticle(filename)` | 6995 | pinned.json write |
| 57 | P2 | `unpinArticle()` | 7029 | pinned.json clear |

---

## ФАЗА 5 — Publishing Pipelines (sessions 58–70)
> Публікація на сайт, Telegram, Threads, планувальник.

| # | Пріоритет | Функція | Лінія | Фокус аудиту |
|---|-----------|---------|-------|--------------|
| 58 | P0 | `triggerManualDeploy()` | 5459 | moderate.yml dispatch |
| 59 | P1 | `deployAll()` | 5434 | Batch queue + deploy |
| 60 | P1 | `postToTelegram()` | 5632 | telegram_post.yml dispatch |
| 61 | P1 | `postToThreads()` | 5741 | threads_post.yml dispatch |
| 62 | P1 | `scheduleArticle(type, idx)` | 5827 | scheduled.json write |
| 63 | P1 | `loadScheduledView()` | 4760 | scheduled.json load + render |
| 64 | P1 | `cancelScheduled(type, id)` | 5910 | scheduled.json delete entry |
| 65 | P2 | `renderQueue()` | 5393 | Website queue UI |
| 66 | P2 | `renderTgQueue()` | 5591 | Telegram queue UI |
| 67 | P2 | `renderThreadsQueue()` | 5700 | Threads queue UI |
| 68 | P2 | `loadQueue()` | 5380 | localStorage read |
| 69 | P2 | `loadTgQueue()` | 5578 | localStorage read |
| 70 | P2 | `loadThreadsQueue()` | 5687 | localStorage read |
| 71 | P2 | `renderScheduledGroup(...)` | 4813 | Render grouped scheduled |
| 72 | P2 | `setSchedulePreset(...)` | 5797 | Time preset logic |

---

## ФАЗА 6 — Social Status (sessions 73–77)

| # | Пріоритет | Функція | Лінія | Фокус аудиту |
|---|-----------|---------|-------|--------------|
| 73 | P1 | `openSocialModal(filename, platform)` | 8260 | Modal open + data load |
| 74 | P1 | `publishSocial()` | 8332 | Social publish dispatch |
| 75 | P2 | `loadSocialStatus()` | 8246 | social_status.json load |
| 76 | P2 | `closeSocialModal()` | 8327 | Modal close + cleanup |

---

## ФАЗА 7 — Analytics & Calendar (sessions 78–84)

| # | Пріоритет | Функція | Лінія | Фокус аудиту |
|---|-----------|---------|-------|--------------|
| 77 | P1 | `renderStats()` | 7158 | Stats calculation + chart render |
| 78 | P2 | `initCalendar()` | 7236 | Calendar data init |
| 79 | P2 | `renderCalendar()` | 7260 | Calendar render logic |
| 80 | P2 | `showCalendarDay(dateStr)` | 7314 | Day detail view |
| 81 | P3 | `calendarPrev()` | 7243 | Nav |
| 82 | P3 | `calendarNext()` | 7248 | Nav |
| 83 | P3 | `calendarToday()` | 7253 | Nav |
| 84 | P3 | `timeAgo(dateStr)` | 7350 | Utility formatting |

---

## ФАЗА 8 — Sources / RSS Settings (sessions 85–91)

| # | Пріоритет | Функція | Лінія | Фокус аудиту |
|---|-----------|---------|-------|--------------|
| 85 | P1 | `loadSources()` | 8019 | sources.json load |
| 86 | P1 | `saveSource()` | 8138 | sources.json write, validation |
| 87 | P1 | `toggleSourceActive(idx)` | 8197 | sources.json atomic toggle |
| 88 | P2 | `renderSources()` | 8053 | Table render |
| 89 | P2 | `editSource(idx)` | 8125 | Form population |
| 90 | P2 | `filterSources()` | 8100 | Filter UI |
| 91 | P3 | `toggleSourceAddForm()` | 8104 | Form toggle |

---

## ФАЗА 9 — YouTube Panel (sessions 92–95)

| # | Пріоритет | Функція | Лінія | Фокус аудиту |
|---|-----------|---------|-------|--------------|
| 92 | P1 | `ytPanelSearch()` | 6022 | YouTube API call, error handling, XSS |
| 93 | P1 | `addYtVideo(videoId, mode)` | 6091 | Add video to candidates/workflow |
| 94 | P2 | `runYoutubeMonitor()` | 4736 | Workflow dispatch |
| 95 | P3 | `toggleYtPanel()` | 6008 | Panel toggle |

---

## ФАЗА 10 — Catalog / Companies (sessions 96–104)

| # | Пріоритет | Функція | Лінія | Фокус аудиту |
|---|-----------|---------|-------|--------------|
| 96 | P1 | `loadCatalog()` | 8404 | catalog.json load |
| 97 | P1 | `saveCompany()` | 8631 | catalog.json write, validation |
| 98 | P1 | `deleteCompany(id, name)` | 8721 | Delete + confirm |
| 99 | P1 | `saveCatalogData(msg)` | 8422 | Internal write |
| 100 | P2 | `renderCompanies()` | 8464 | Table render |
| 101 | P2 | `editCompany(id)` | 8578 | Form population |
| 102 | P2 | `uploadCatalogLogo(fileInput)` | 8602 | Image upload |
| 103 | P2 | `showCompanyForm(id)` | 8525 | Form show |
| 104 | P3 | `triggerCatalogDeploy()` | 8729 | Workflow dispatch |

---

## ФАЗА 11 — KB Articles (sessions 105–114)

| # | Пріоритет | Функція | Лінія | Фокус аудиту |
|---|-----------|---------|-------|--------------|
| 105 | P1 | `loadKnowledge()` | 8799 | KB load |
| 106 | P1 | `saveKbArticle()` | 8968 | KB write, validation |
| 107 | P1 | `deleteKbArticle(filename, sha)` | 9041 | KB delete |
| 108 | P1 | `kbAutoFormat()` | 9206 | Gemini format |
| 109 | P2 | `renderKbList()` | 8870 | Table render |
| 110 | P2 | `showKbEditor(filename)` | 8908 | Editor open |
| 111 | P2 | `uploadKbImage(fileInput)` | 9057 | Image upload |
| 112 | P3 | `insertKbTable()` | 9116 | Markdown insert |
| 113 | P3 | `insertKbDivider()` | 9127 | Markdown insert |
| 114 | P3 | `closeKbEditor()` | 8961 | Close + cleanup |

---

## ФАЗА 12 — KB Links (sessions 115–122)

| # | Пріоритет | Функція | Лінія | Фокус аудиту |
|---|-----------|---------|-------|--------------|
| 115 | P1 | `loadKbLinks()` | 9276 | kb_links.json load |
| 116 | P1 | `saveKbLinks(msg)` | 9334 | kb_links.json write |
| 117 | P1 | `saveKbLinkEntry()` | 9398 | Validation + write |
| 118 | P1 | `deleteKbLinkEntry(idx)` | 9426 | Delete |
| 119 | P2 | `renderKbLinks()` | 9292 | List render |
| 120 | P2 | `showKbLinkForm(idx)` | 9348 | Form |
| 121 | P2 | `confirmInsertKbLink()` | 9192 | Modal confirm |
| 122 | P3 | `openKbLinkModal()` | 9138 | Modal open |
| 123 | P3 | `filterKbLinkList()` | 9154 | Filter |

---

## ФАЗА 13 — Utilities & Misc (sessions 123–124)

| # | Пріоритет | Функція | Лінія | Фокус аудиту |
|---|-----------|---------|-------|--------------|
| 124 | P2 | `slugifyUA(text)` | 6460 | Ukrainian slug generation |
| 125 | P2 | `markdownToHtml(md)` | 6327 | Markdown parser completeness |
| 126 | P2 | `renderRelevanceStars(score)` | 7470 | Star rendering |

---

## Шаблон одної сесії (copy-paste для кожного запиту)

```
СЕСІЯ #[N] — [назва функції] (лінія [X])

ЧИТАЄМО:
- Поточний код функції повністю
- Всі місця де вона викликається
- Всі файли які вона читає/пише

АНАЛІЗУЄМО по 8 точках:
[ ] CORRECTNESS
[ ] ERROR HANDLING  
[ ] RACE CONDITIONS
[ ] PERFORMANCE
[ ] UX
[ ] SECURITY
[ ] CODE CLARITY
[ ] DEAD CODE

ОЦІНКА: 🔴 / 🟡 / 🟢

ЗМІНИ: [конкретні diff або "no changes needed"]

ДЕПЛОЙ (обов'язково після кожної сесії):
→ hugo --gc --minify       (перевірка build)
→ git add layouts/admin/list.html
→ git commit -m "⚡ Audit #N: ..."
→ git pull --rebase origin main && git push origin main
→ оновити AUDIT_PLAN.md статус: ⬜ → ✅
```

---

## Статус прогресу

| Фаза | Сесій | Статус |
|------|-------|--------|
| Фаза 1: Core Infrastructure | 1–9 | ✅ 6/9 завершено (ghApi, b64, parseFrontmatter, showStatus, checkAuth+init+logout, showView+updateBadges) |
| Фаза 2: Feed / Candidates | 10–26 | ✅ 17/17 ЗАВЕРШЕНО (loadCandidates, appendYouTubeDraftsToCandidates, addToProcessed, deleteCandidate, deleteSelectedCandidates, deleteDraftArticleByFilename, _shortlistCandidates, renderCandidates, shortlistCandidate+shortlistSelected, processCandidates, refreshCandidates 🟢, updateCandidatesCounter, candidateToggle 🟢, candidatesToggleAll 🟢, filterCandidates 🟢, toggleCandidatePreview 🟢) |
| Фаза 3: Editorial / Workflow | 27–42 | ✅ 16/16 ЗАВЕРШЕНО (saveWorkflowData 🟢, loadWorkflowArticles ✅, loadEditorial 🟢, renderEditorial ✅, processWorkflowItem 🟢, processQueuedWorkflow ✅, removeWorkflowItem 🟢, _removeFromWorkflow 🟢, quickAddUrl ✅, _tryResolveGoogleNewsUrl 🟢, retryProcessing ✅, switchEditorialTab 🟢, updateEditorialCounter 🟢, toggleQuickAdd 🟢, resolveGoogleNewsInCard 🟢, saveArticleUrl ✅) |
| Фаза 4: Drafts & Articles | 43–57 | ✅ 15/15 ЗАВЕРШЕНО (approveArticle ✅, deleteArticle 🟢, removeDraftEntry 🟢, createArticle ✅, editArticle ✅, loadDrafts 🟡, renderArticles 🟡, filterArticles 🟢, autoFormat ✅, toggleCreateForm 🟢, resetCreateForm 🟢, initQuill 🟢, generateImage ✅, uploadImage 🟡, pinArticle 🟢, unpinArticle 🟢) |
| Фаза 5: Publishing | 58–72 | ✅ 15/15 ЗАВЕРШЕНО (triggerManualDeploy 🟢, deployAll 🟢, postToTelegram 🟢, postToThreads 🟢, scheduleArticle 🟢, loadScheduledView 🟡, cancelScheduled 🟡, renderQueue 🟢, renderTgQueue 🟢, renderThreadsQueue 🟢, loadQueue 🟢, loadTgQueue 🟢, loadThreadsQueue 🟢, renderScheduledGroup 🟢, setSchedulePreset 🟡) |
| Фаза 6: Social Status | 73–76 | ✅ 4/4 ЗАВЕРШЕНО (openSocialModal 🟡, publishSocial 🟡, loadSocialStatus 🟢, closeSocialModal 🟢) |
| Фаза 7: Analytics | 77–84 | ✅ 8/8 (renderStats 🟡, initCalendar 🟢, renderCalendar 🟢, showCalendarDay 🟢, calendarPrev 🟢, calendarNext 🟢, calendarToday 🟢, timeAgo 🟡) |
| Фаза 8: Sources | 85–91 | ✅ 7/7 (loadSources 🟢, saveSource 🟡, toggleSourceActive 🟡, renderSources 🟢, editSource 🟢, filterSources 🟢, toggleSourceAddForm 🟢) |
| Фаза 9: YouTube Panel | 92–95 | ✅ 4/4 (ytPanelSearch 🟢, addYtVideo 🟡, runYoutubeMonitor 🟢, toggleYtPanel 🟢) |
| Фаза 10: Catalog | 96–104 | ✅ 9/9 (loadCatalog 🟡, saveCatalogData 🟢, renderCompanies 🟡, editCompany 🟢, showCompanyForm 🟢, uploadCatalogLogo 🟡, saveCompany 🟡, deleteCompany 🟢, triggerCatalogDeploy 🟢) |
| Фаза 11: KB Articles | 105–114 | 🔄 4/10 (loadKnowledge 🟢, saveKbArticle 🟡, deleteKbArticle 🟢, kbAutoFormat 🟡) |
| Фаза 12: KB Links | 115–123 | ⬜ Не почато |
| Фаза 13: Utilities | 124–126 | ⬜ Не почато |
| **ВСЬОГО** | **126 сесій** | **97/126** |

---

## Як запускати сесії

```
"Аудит #1 — ghApi"
"Аудит #2 — b64DecodeUtf8"
...
"Аудит #10 — loadCandidates"
```

Після кожної сесії оновлюємо статус в цьому файлі: ⬜ → ✅

---

*Документ створено: 2026-04-11*
*Стандарт: Apple Engineering Quality*
*Файл: AUDIT_PLAN.md*
