import { useState } from 'react'
import { useAppStore } from '../store/appStore'
import UploadModal from '../upload/UploadModal'
import Recent from '../recent/Recent'
import Library from '../library/Library'

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

const LIBRARY_ITEMS = ['Search', 'Recent', 'Library', 'Folders', 'Pinned']
const SYSTEM_ITEMS = ['Settings', 'Export']

/** Оболочка сайдбара: навигация + переключение view (Player / Knowledge Graph). */
export default function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const mainView = useAppStore((s) => s.mainView)
  const setMainView = useAppStore((s) => s.setMainView)
  const isProcessing = useAppStore((s) => s.isProcessing)
  const progress = useAppStore((s) => s.progress)

  const [uploadOpen, setUploadOpen] = useState(false)

  const itemClass = (active: boolean) =>
    `w-full truncate px-3 py-1.5 text-left text-[13px] transition-colors ${
      active
        ? 'bg-bg-card text-accent'
        : 'text-text-secondary hover:bg-bg-card hover:text-text-primary'
    }`

  return (
    <aside
      className={`sidebar-root glass-panel flex h-full shrink-0 flex-col border-r transition-[width] duration-200 ${
        collapsed ? 'w-[52px]' : 'w-[240px]'
      }`}
    >
      <div className="flex h-12 items-center justify-between border-b border-border-glass px-3">
        {!collapsed && (
          <span className="text-sm font-semibold text-accent">VideoEssence</span>
        )}
        <button
          type="button"
          onClick={onToggle}
          title={collapsed ? 'Развернуть' : 'Свернуть'}
          className="text-text-muted hover:text-text-primary"
        >
          {collapsed ? '»' : '«'}
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto py-2">
        {!collapsed && (
          <div className="px-3 py-1 text-[10px] uppercase tracking-wide text-text-faint">
            Actions
          </div>
        )}
        {['New Session', 'Upload Video', 'Upload Doc', 'Paste URL'].map((item) => (
          <button
            key={item}
            type="button"
            title={item}
            onClick={
              item === 'Upload Video' || item === 'Paste URL'
                ? () => setUploadOpen(true)
                : undefined
            }
            className={itemClass(false)}
          >
            {collapsed ? item[0] : item}
          </button>
        ))}

        {!collapsed && (
          <div className="px-3 py-1 text-[10px] uppercase tracking-wide text-text-faint">
            Library
          </div>
        )}
        {isProcessing && !collapsed ? (
          <div className="mx-3 my-1 rounded-md border border-accent/40 bg-accent-glow px-2 py-2">
            <div className="text-[11px] text-accent">Processing…</div>
            <div className="text-[11px] tabular-nums text-text-secondary">
              {progress || 'queued'}
            </div>
          </div>
        ) : (
          LIBRARY_ITEMS.map((item) =>
            item === 'Recent' ? (
              <Recent key={item} collapsed={collapsed} />
            ) : item === 'Library' ? (
              <Library key={item} collapsed={collapsed} />
            ) : (
              <button key={item} type="button" title={item} className={itemClass(false)}>
                {collapsed ? item[0] : item}
              </button>
            ),
          )
        )}

        {!collapsed && (
          <div className="px-3 py-1 text-[10px] uppercase tracking-wide text-text-faint">
            System
          </div>
        )}
        {SYSTEM_ITEMS.map((item) => (
          <button key={item} type="button" title={item} className={itemClass(false)}>
            {collapsed ? item[0] : item}
          </button>
        ))}

        {!collapsed && (
          <div className="px-3 py-1 text-[10px] uppercase tracking-wide text-text-faint">
            Views
          </div>
        )}
        <button
          type="button"
          title="Player"
          onClick={() => setMainView('player')}
          className={itemClass(mainView === 'player')}
        >
          {collapsed ? '▶' : 'Player'}
        </button>
        <button
          type="button"
          title="Knowledge Graph"
          onClick={() => setMainView('graph')}
          className={itemClass(mainView === 'graph')}
        >
          {collapsed ? '◉' : 'Knowledge Graph'}
        </button>
      </nav>

      <UploadModal open={uploadOpen} onClose={() => setUploadOpen(false)} />
    </aside>
  )
}
