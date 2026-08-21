import { useState } from 'react'
import { useAppStore } from '../store/appStore'
import UploadModal from '../upload/UploadModal'
import Recent from '../recent/Recent'
import Library from '../library/Library'

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

export default function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const mainView = useAppStore((s) => s.mainView)
  const setMainView = useAppStore((s) => s.setMainView)
  const isProcessing = useAppStore((s) => s.isProcessing)
  const progress = useAppStore((s) => s.progress)

  const [uploadOpen, setUploadOpen] = useState(false)

  const itemClass = (active = false) =>
    `w-full truncate px-3 py-1.5 text-left text-[13px] transition-colors ${
      active
        ? 'bg-bg-card text-accent'
        : 'text-text-secondary hover:bg-bg-card hover:text-text-primary'
    }`

  const sectionClass =
    'px-3 pb-1 pt-3 text-[10px] uppercase tracking-[0.08em] text-text-faint'

  if (collapsed) {
    return (
      <aside className="sidebar-root glass-panel flex h-full w-[52px] shrink-0 flex-col border-r">
        <div className="flex h-12 items-center justify-center border-b border-border-glass">
          <button
            type="button"
            onClick={onToggle}
            title="Развернуть"
            className="text-text-muted transition-colors hover:text-text-primary"
          >
            »
          </button>
        </div>

        <nav className="flex flex-1 flex-col items-center py-2">
          <button
            type="button"
            onClick={() => setUploadOpen(true)}
            title="New"
            className="mb-2 flex h-8 w-8 items-center justify-center rounded text-lg text-accent transition-colors hover:bg-bg-card"
          >
            +
          </button>

          <button
            type="button"
            title="Search"
            className="flex h-8 w-8 items-center justify-center rounded text-text-muted hover:bg-bg-card hover:text-text-primary"
          >
            ⌕
          </button>

          <button
            type="button"
            title="Player"
            onClick={() => setMainView('player')}
            className={`mt-auto flex h-8 w-8 items-center justify-center rounded ${
              mainView === 'player'
                ? 'bg-bg-card text-accent'
                : 'text-text-muted hover:bg-bg-card hover:text-text-primary'
            }`}
          >
            ▶
          </button>

          <button
            type="button"
            title="Knowledge Graph"
            onClick={() => setMainView('graph')}
            className={`mt-1 flex h-8 w-8 items-center justify-center rounded ${
              mainView === 'graph'
                ? 'bg-bg-card text-accent'
                : 'text-text-muted hover:bg-bg-card hover:text-text-primary'
            }`}
          >
            ◎
          </button>
        </nav>

        <UploadModal
          open={uploadOpen}
          onClose={() => setUploadOpen(false)}
        />
      </aside>
    )
  }

  return (
    <aside className="sidebar-root glass-panel flex h-full w-[240px] shrink-0 flex-col border-r">
      {/* Header */}
      <div className="flex h-12 items-center justify-between border-b border-border-glass px-3">
        <span className="text-sm font-semibold tracking-tight text-accent">
          VideoEssence
        </span>

        <button
          type="button"
          onClick={onToggle}
          title="Свернуть"
          className="text-text-muted transition-colors hover:text-text-primary"
        >
          «
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto py-2">
        {/* New */}
        <div className="px-2 pb-2">
          <button
            type="button"
            onClick={() => setUploadOpen(true)}
            className="flex w-full items-center gap-2 rounded-md border border-border-glass bg-bg-card px-3 py-2 text-left text-[13px] text-text-primary transition-colors hover:border-accent/40 hover:bg-bg-card"
          >
            <span className="text-base leading-none text-accent">＋</span>
            <span>New</span>
          </button>
        </div>

        {/* Processing */}
        {isProcessing && (
          <div className="mx-3 mb-2 rounded-md border border-accent/30 bg-accent-glow px-2.5 py-2">
            <div className="text-[11px] text-accent">Processing…</div>
            <div className="mt-0.5 text-[11px] tabular-nums text-text-secondary">
              {progress || 'queued'}
            </div>
          </div>
        )}

        {/* Library */}
        <div className={sectionClass}>Library</div>

        <button
          type="button"
          title="Search"
          className={itemClass()}
        >
          <span className="mr-2 text-text-muted">⌕</span>
          Search
        </button>

        <Recent collapsed={false} />

        <Library collapsed={false} />

        <button
          type="button"
          title="Folders"
          className={itemClass()}
        >
          <span className="mr-2 text-text-muted">▸</span>
          Folders
        </button>

        <button
          type="button"
          title="Pinned"
          className={itemClass()}
        >
          <span className="mr-2 text-text-muted">★</span>
          Pinned
        </button>

        {/* Views */}
        <div className={sectionClass}>Views</div>

        <button
          type="button"
          title="Player"
          onClick={() => setMainView('player')}
          className={itemClass(mainView === 'player')}
        >
          <span className="mr-2">▶</span>
          Player
        </button>

        <button
          type="button"
          title="Knowledge Graph"
          onClick={() => setMainView('graph')}
          className={itemClass(mainView === 'graph')}
        >
          <span className="mr-2">◎</span>
          Knowledge Graph
        </button>
      </nav>

      {/* Bottom */}
      <div className="border-t border-border-glass px-2 py-2">
        <button
          type="button"
          title="Settings"
          className={itemClass()}
        >
          <span className="mr-2 text-text-muted">⚙</span>
          Settings
        </button>
      </div>

      <UploadModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
      />
    </aside>
  )
}