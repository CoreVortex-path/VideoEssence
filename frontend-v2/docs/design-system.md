# Design System

## Технологии
- React 18 + TypeScript + Vite
- Tailwind CSS (без UI-библиотек)
- Zustand (глобальный стейт)
- TanStack Query (серверный стейт)
- React Router (или wouter)

## CSS-переменные (тёмная тема)
--bg-primary: #0c0a0f
--bg-secondary: #121018
--bg-glass: rgba(18,16,24,0.72)
--bg-card: rgba(255,255,255,0.04)
--border-glass: rgba(255,255,255,0.06)
--border-primary: rgba(255,255,255,0.14)
--text-primary: #f0e6f5
--text-secondary: #c8bdd0
--text-muted: #a29aac
--text-dim: #9b92a6
--text-faint: #4a4252
--accent: #14b8a6
--accent-hover: #0d9488
--accent-glow: rgba(20,184,166,0.20)
--amber: #f59e0b
--purple: #a855f7
--cyan: #06b6d4

## Layout
- Sidebar: 240px (сворачивается до 52px), слева, glassmorphism
- Main: flex-1, колонка (player сверху, контент снизу)
- Right Panel: 340px min, resizable, glassmorphism, табы внутри
- Resize handles: 4px, hover → accent цвет
- Zen mode: скрывает sidebar, panels, controls; video max-height 55vh

## Типографика
- Font: Inter (Google Fonts)
- Base: 14px, line-height 1.6
- Tabular nums для таймстампов
- Шкала — классы в `src/index.css` (`@layer components`), задают только размер/вес/цвет:
  `.t-page-title` (19/600), `.t-section-title` (12/600 uppercase, заголовки секций),
  `.t-card-title` (15/500, названия документов/карточек), `.t-body` (14, основной текст),
  `.t-secondary` (14, вторичный текст), `.t-meta` (12.5, метаданные), `.t-caption` (12, подписи/пустые состояния).
- Минимальный размер в UI — 12px; ad-hoc `text-[Npx]` вне шкалы не используем
  (исключения: глифы-иконки и акцентные статусы, но не мельче 12px).
- `text-faint` — только плейсхолдеры/декоративные глифы; читаемый текст — не ниже `text-dim`.

## Глобальные поведения
- Command Palette: Ctrl+K, ESC закрыть
- Zen Mode: клавиша Z
- Play/Pause: Space (когда не в поле ввода)
- Скроллбары: тонкие, прозрачный трек