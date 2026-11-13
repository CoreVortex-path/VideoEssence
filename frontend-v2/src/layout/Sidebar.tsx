import { useState } from 'react'
import { useAppStore } from '../store/appStore'
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  FolderIcon,
  GraphIcon,
  PlayIcon,
  PlusIcon,
  SearchIcon,
  SettingsIcon,
} from '../pdf/icons'
import UploadModal from '../upload/UploadModal'
import Recent from '../recent/Recent'
import Library from '../library/Library'

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
  /** Ширина развёрнутой панели в px (drag-ресайз в AppLayout). */
  width: number
}

/** Слот фиксированной ширины для иконки пункта меню — текст пунктов стоит ровной колонкой. */
function IconSlot({ children, muted = false }: { children: React.ReactNode; muted?: boolean }) {
  return (
    <span
      className={`mr-2 flex w-5 shrink-0 items-center justify-center ${muted ? 'text-text-muted' : ''}`}
    >
      {children}
    </span>
  )
}

export default function Sidebar({ collapsed, onToggle, width }: SidebarProps) {
  const mainView = useAppStore((s) => s.mainView)
  const setMainView = useAppStore((s) => s.setMainView)
  const isProcessing = useAppStore((s) => s.isProcessing)
  const progress = useAppStore((s) => s.progress)

  const [uploadOpen, setUploadOpen] = useState(false)

  const itemClass = (active = false) =>
    `t-body flex w-full items-center truncate px-3 py-1.5 text-left transition-colors ${
      active
        ? 'bg-bg-card text-accent'
        : 'text-text-secondary hover:bg-bg-card hover:text-text-primary'
    }`

  const sectionClass = 't-section-title px-3 pb-1 pt-3'

  if (collapsed) {
    return (
      <aside className="sidebar-root glass-panel flex h-full w-[52px] shrink-0 flex-col border-r">
        <div className="flex h-12 items-center justify-center border-b border-border-glass">
          <button
            type="button"
            onClick={onToggle}
            title="Развернуть"
            className="flex h-8 w-8 items-center justify-center rounded text-text-muted transition-colors hover:text-text-primary"
          >
            <ChevronRightIcon className="h-4 w-4" />
          </button>
        </div>

        <nav className="flex flex-1 flex-col items-center py-2">
          <button
            type="button"
            onClick={() => setUploadOpen(true)}
            title="New"
            className="mb-2 flex h-8 w-8 items-center justify-center rounded text-accent transition-colors hover:bg-bg-card"
          >
            <PlusIcon className="h-4 w-4" />
          </button>

          <button
            type="button"
            title="Search"
            className="flex h-8 w-8 items-center justify-center rounded text-text-muted hover:bg-bg-card hover:text-text-primary"
          >
            <SearchIcon className="h-4 w-4" />
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
            <PlayIcon className="h-4 w-4" />
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
            <GraphIcon className="h-4 w-4" />
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
    <aside
      className="sidebar-root glass-panel flex h-full shrink-0 flex-col border-r"
      style={{ width }}
    >      {/* Header */}
      <div className="flex h-12 items-center justify-between border-b border-border-glass px-3">
        <span className="text-sm font-semibold tracking-tight text-accent">
          VideoEssence
        </span>

        <button
          type="button"
          onClick={onToggle}
          title="Свернуть"
          className="flex h-8 w-8 items-center justify-center rounded text-text-muted transition-colors hover:text-text-primary"
        >
          <ChevronLeftIcon className="h-4 w-4" />
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto py-2">
        {/* New */}
        <div className="px-2 pb-2">
          <button
            type="button"
            onClick={() => setUploadOpen(true)}
            className="t-body flex w-full items-center gap-2 rounded-md border border-border-glass bg-bg-card px-3 py-2 text-left transition-colors hover:border-accent/40 hover:bg-bg-card"
          >
            <span className="flex w-5 shrink-0 items-center justify-center text-accent">
              <PlusIcon className="h-4 w-4" />
            </span>
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
          <IconSlot muted>
            <SearchIcon className="h-4 w-4" />
          </IconSlot>
          Search
        </button>

        <Recent collapsed={false} />

        <Library collapsed={false} />

        <button
          type="button"
          title="Folders"
          className={itemClass()}
        >
          <IconSlot muted>
            <FolderIcon className="h-4 w-4" />
          </IconSlot>
          Folders
        </button>

        {/* Views */}
        <div className={sectionClass}>Views</div>

        <button
          type="button"
          title="Player"
          onClick={() => setMainView('player')}
          className={itemClass(mainView === 'player')}
        >
          <IconSlot>
            <PlayIcon className="h-4 w-4" />
          </IconSlot>
          Player
        </button>

        <button
          type="button"
          title="Knowledge Graph"
          onClick={() => setMainView('graph')}
          className={itemClass(mainView === 'graph')}
        >
          <IconSlot>
            <GraphIcon className="h-4 w-4" />
          </IconSlot>
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
          <IconSlot muted>
            <SettingsIcon className="h-4 w-4" />
          </IconSlot>
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
