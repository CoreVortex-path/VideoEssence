# Component Specification

## Layout
- AppLayout: Sidebar + ResizeHandle + Main + ResizeHandle + RightPanel
- Sidebar: Logo, New Session, Upload Video, Upload Doc, Paste URL, Search, Recent list, Folders, Views (Knowledge Graph), Pinned, Settings/Models, Export. Сворачивается.
- RightPanel: Табы (AI, Bookmarks, Notes, Thesaurus). Resizable width. Расширяемая.

## Player Area (верх, фиксированная высота)
- VideoStage: aspect-ratio 16/9, max-height 280px, кнопка play с SVG progress ring
- Waveform: 60 баров, flex row, gap 2px, height 28px
- ChapterBar: 5 сегментов, hover tooltip с title+time, click → seek
- PlayerControls: play button, time display (tabular), speed select (0.5-2x), fullscreen

## Content Area (табы)
- Tabs: Transcript | Summary | Translation
- TranscriptView: скроллируемый список сегментов
  - Entry: timestamp (кликабельный, seek), text (hover highlight), inline translate (click toggle), bookmark button
  - Текущий сегмент: левая рамка accent цвета, автоскролл к центру во время воспроизведения
  - InlineToolbar при выделении текста: Ask AI | Note | Highlight
- SummaryView: статичный текст
- TranslationView: 2-колоночная сетка (original left, translated right), sticky headers

## Правая панель (табы)
- AI Chat:
  - Список сообщений (user справа/градиент, assistant слева/card)
  - Индикатор печати (3 точки)
  - Textarea + send button
  - Кнопка расширения: 3 состояния (normal 340px → wide 560px → fullscreen 100vw). НИКАКОГО info-box о текущем сегменте внизу.
  - Автоскролл к новым сообщениям вниз.
- Notes:
  - Кнопка Add Note
  - NoteItem: drag handle, time, title (dblclick edit), text (edit), delete
  - Drag-and-drop reorder (native HTML5 DnD)
- Bookmarks: список time+text, click → seek
- Thesaurus:
  - Search input + Add button
  - Карточка: flip-анимация (front: word, synonyms, related, color dots; back: definition)
  - Добавление synonym/related word

## Глобальные оверлеи
- CommandPalette: fixed center-top, search input, список команд, keyboard nav (стрелки+enter)
- ZenHint: bottom center, показывает hotkeys

## Правила
- НЕТ mini-player (video всегда фиксирован сверху)
- Транскрипт автоскроллится к активному сегменту (block: center)
- Все анимации через CSS (без Framer Motion)