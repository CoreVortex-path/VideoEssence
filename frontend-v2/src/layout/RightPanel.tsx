import type { ReactNode } from 'react'
import { useAppStore } from '../store/appStore'
import type { RightPanelTab } from '../store/appStore'
import FloatingPanel from '../components/FloatingPanel'
import ChatPanel from '../chat/ChatPanel'
import NotesPanel from '../notes/NotesPanel'
import BookmarksPanel from '../bookmarks/BookmarksPanel'
import ThesaurusPanel from '../thesaurus/ThesaurusPanel'

/** Inline-иконки полоски в стиле pdf/icons.tsx (24 viewBox, stroke = currentColor). */
function iconBase(className?: string) {
  return {
    className: className ?? 'h-5 w-5',
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
  }
}

function AiGlyph({ className }: { className?: string }) {
  return (
    <svg {...iconBase(className)}>
      <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z" />
      <path d="M19 16l.9 2.1L22 19l-2.1.9L19 22l-.9-2.1L16 19l2.1-.9L19 16z" />
    </svg>
  )
}

function BookmarkGlyph({ className }: { className?: string }) {
  return (
    <svg {...iconBase(className)}>
      <path d="M7 4h10a1 1 0 011 1v15l-6-4-6 4V5a1 1 0 011-1z" />
    </svg>
  )
}

function NoteGlyph({ className }: { className?: string }) {
  return (
    <svg {...iconBase(className)}>
      <path d="M6 3h9l4 4v14H6V3z" />
      <path d="M15 3v4h4M9 12h6M9 16h4" />
    </svg>
  )
}

function BookGlyph({ className }: { className?: string }) {
  return (
    <svg {...iconBase(className)}>
      <path d="M12 5c-2-1.5-5-1.5-8-1v14c3-.5 6-.5 8 1 2-1.5 5-1.5 8-1V4c-3 .5-6 .5-8 1z" />
      <path d="M12 5v14" />
    </svg>
  )
}

const TABS: { id: RightPanelTab; label: string; icon: ReactNode }[] = [
  { id: 'ai', label: 'AI', icon: <AiGlyph /> },
  { id: 'bookmarks', label: 'Bookmarks', icon: <BookmarkGlyph /> },
  { id: 'notes', label: 'Notes', icon: <NoteGlyph /> },
  { id: 'thesaurus', label: 'Thesaurus', icon: <BookGlyph /> },
]

/**
 * Правая сторона: вертикальная полоска иконок (48px, в потоке flex) +
 * floating-панель активного таба (оверлей поверх main).
 * Клик по иконке открывает панель, повторный клик по активной — закрывает.
 */
export default function RightPanel() {
  const rightPanelTab = useAppStore((s) => s.rightPanelTab)
  const rightPanelOpen = useAppStore((s) => s.rightPanelOpen)
  const setRightPanelTab = useAppStore((s) => s.setRightPanelTab)
  const setRightPanelOpen = useAppStore((s) => s.setRightPanelOpen)

  const activeTab = TABS.find((t) => t.id === rightPanelTab) ?? TABS[0]

  const onIconClick = (id: RightPanelTab) => {
    if (rightPanelOpen && id === rightPanelTab) setRightPanelOpen(false)
    else setRightPanelTab(id)
  }

  return (
    <>
      <aside className="glass-panel flex h-full w-[48px] shrink-0 flex-col items-center border-l py-2">
        {TABS.map((tab) => {
          const isActive = rightPanelOpen && tab.id === rightPanelTab
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => onIconClick(tab.id)}
              title={tab.label}
              className={`mb-1 flex h-9 w-9 items-center justify-center rounded transition-colors ${
                isActive
                  ? 'bg-accent/15 text-accent'
                  : 'text-text-muted hover:bg-bg-card hover:text-text-primary'
              }`}
            >
              {tab.icon}
            </button>
          )
        })}
      </aside>

      {rightPanelOpen && (
        <FloatingPanel title={activeTab.label} onClose={() => setRightPanelOpen(false)}>
          {rightPanelTab === 'ai' && <ChatPanel />}
          {rightPanelTab === 'bookmarks' && <BookmarksPanel />}
          {rightPanelTab === 'notes' && <NotesPanel />}
          {rightPanelTab === 'thesaurus' && <ThesaurusPanel />}
        </FloatingPanel>
      )}
    </>
  )
}
