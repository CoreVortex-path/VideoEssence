import { useAppStore } from '../store/appStore'
import ChatPanel from '../chat/ChatPanel'
import NotesPanel from '../notes/NotesPanel'
import BookmarksPanel from '../bookmarks/BookmarksPanel'
import ThesaurusPanel from '../thesaurus/ThesaurusPanel'

const TABS = [
  { id: 'ai', label: 'AI' },
  { id: 'bookmarks', label: 'Bookmarks' },
  { id: 'notes', label: 'Notes' },
  { id: 'thesaurus', label: 'Thesaurus' },
] as const

/** Правая панель: табы + контент активного таба. */
export default function RightPanel({ width }: { width: number | string }) {
  const rightPanelTab = useAppStore((s) => s.rightPanelTab)
  const setRightPanelTab = useAppStore((s) => s.setRightPanelTab)

  return (
    <aside
      className="glass-panel flex h-full shrink-0 flex-col border-l"
      style={{ width }}
    >
      <div className="flex border-b border-border-glass">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setRightPanelTab(tab.id)}
            className={`flex-1 px-2 py-2 text-[12px] transition-colors ${
              rightPanelTab === tab.id
                ? 'border-b-2 border-accent text-text-primary'
                : 'text-text-muted hover:text-text-secondary'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex min-h-0 flex-1 flex-col">
        {rightPanelTab === 'ai' && <ChatPanel />}
        {rightPanelTab === 'bookmarks' && <BookmarksPanel />}
        {rightPanelTab === 'notes' && <NotesPanel />}
        {rightPanelTab === 'thesaurus' && <ThesaurusPanel />}
      </div>
    </aside>
  )
}
