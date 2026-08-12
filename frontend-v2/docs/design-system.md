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
--border-primary: rgba(255,255,255,0.08)
--text-primary: #f0e6f5
--text-secondary: #c8bdd0
--text-muted: #948a9c
--text-dim: #6b6275
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
- Base: 13-14px, line-height 1.6
- Tabular nums для таймстампов

## Глобальные поведения
- Command Palette: Ctrl+K, ESC закрыть
- Zen Mode: клавиша Z
- Play/Pause: Space (когда не в поле ввода)
- Скроллбары: тонкие, прозрачный трек