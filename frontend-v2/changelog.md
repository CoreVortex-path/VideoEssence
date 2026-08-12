# CHANGELOG — Translation & ContentArea Refactor

## Общая цель
Перевод (Translation) вынесен из вкладки в таб-бар, добавлен выбор языка, inline-перевод по клику на фразу в транскрипте, двухколоночный вид Translation без таймкодов.

---

## 1. src/store/appStore.ts

### Добавлено в interface AppState:
- `targetLanguage: string`
- `isTranslating: boolean`
- `translateError: string | null`
- `segmentCache: Record<string, string>`
- `setTargetLanguage: (lang: string) => void`
- `setIsTranslating: (v: boolean) => void`
- `setTranslateError: (err: string | null) => void`
- `cacheSegmentTranslation: (key: string, value: string) => void`

### Изменено:
- Замыкание `create<AppState>((set) => ({` → `create<AppState>((set, get) => ({`
- `setCurrentTask`: теперь восстанавливает `translationSegments` из `task.translation_results` с учётом `targetLanguage` (ищет по выбранному языку → fallback 'ru' → первый доступный). Учитывает структуру бэкенда `{lang: {transcript_segments: []}}`.

---

## 2. src/api/client.ts

### Добавлено:
- `translateText(text, targetLanguage)` — добавлена и затем УДАЛЕНА (бэкенд возвращает 404 на `/translate`).

### Оставлено без изменений:
- `translateTranscript(taskId, targetLanguage)` — основной эндпоинт для полного перевода.

---

## 3. src/layout/ContentArea.tsx

### Изменено:
- Таб-бар теперь `flex items-center justify-between` — табы слева, действия справа.
- Добавлен селект языка: **RU / EN / FR / ZH / DE**.
- Добавлена кнопка **🌐 Translate** с логикой мутации (была внутри TranslationView).
- Кнопка активна только при `taskId && isCompleted`.
- Показывает `isTranslating` → "Translating…".
- Показывает `translateError` строкой под таб-баром.

### Удалено:
- Простой рендер табов без действий.

---

## 4. src/transcript/TranslationView.tsx

### Изменено:
- Убрана кнопка "Translate to RU" (перенесена в ContentArea).
- Убрана таблица с таймкодами.
- Теперь **две колонки сплошным текстом**: `Original` (левая) и `LANG` (правая).
- Левая колонка: `transcriptSegments.map(s => s.text).join(' ')`.
- Правая колонка: `translationSegments.map(s => s.enrichment?.translation || s.text).join(' ')`.
- Sticky-заголовки колонок.
- Состояния: "Process a video first", "Translation will appear after processing…".

---

## 5. src/transcript/TranscriptSegment.tsx

### Изменено:
- Убран локальный стейт `showTranslation` и `bookmarked`.
- Убрана кнопка 🌐 (перевод теперь по клику на весь сегмент).
- Добавлен проп `onTranslate?: () => void`.
- Добавлен `cursor-pointer` и `onClick={onTranslate}` на корневом div.
- Перевод (`translation?: string | null`) приходит пропсом и рендерится с `border-l-2 border-accent`.
- Клик по timestamp не вызывает перевод (`e.stopPropagation()`).

---

## 6. src/transcript/TranscriptView.tsx

### Добавлено:
- `handleTranslate(idx, text)` — по клику на сегмент:
  - Сначала ищет перевод в `translationSegments[idx]?.enrichment?.translation`.
  - Если найден — кладёт в `segmentCache` (показывается inline).
  - Если нет — ранее пытался дергать `translateText` (удалено, т.к. 404).
- `segmentCache` используется для хранения inline-переводов по ключу `{idx}:{lang}`.
- Inline-перевод подставляется только из `segmentCache` (не автоматом для всех).

### Изменено:
- `TranscriptSegment` теперь получает `translation` из `segmentCache[key] ?? null`.
- Убрана кнопка 🌐 внутри сегмента.

---

## 7. src/hooks/useTaskPolling.ts

### Изменено:
- `extractTranslation(results)`: исправлена структура бэкенда. Было `{[lang]: TranscriptSegment[]}` (неверно), стало `{[lang]: {transcript_segments: TranscriptSegment[]}}`.
- При `status === 'failed'` теперь тоже сохраняет `transcriptSegments` и `translationSegments` (частичные данные не теряются).

---

## 8. src/summary/SummaryView.tsx

### Добавлено:
- Обработка `status === 'failed'` — показывает "Summary unavailable" + текст ошибки.
- Рендер `task.summary` при `completed`.

---

## 9. tsconfig.app.json

### Добавлено:
- `"ignoreDeprecations": "6.0"` — заглушка deprecation `baseUrl` в TypeScript 6.x.

---

## Быстрый чеклист для проверки

1. [ ] ContentArea: табы + селект языка + кнопка Translate в одном ряду.
2. [ ] Translation: две колонки, сплошной текст, без таймкодов.
3. [ ] Transcript: клик по фразе → появляется inline-перевод (только для кликнутой).
4. [ ] Смена языка в селекте → TranslationView показывает правильный заголовок колонки.
5. [ ] Перезагрузка страницы → `setCurrentTask` восстанавливает перевод из `translation_results`.
6. [ ] Failed-статус → transcript/summary не пропадают, показывается ошибка.