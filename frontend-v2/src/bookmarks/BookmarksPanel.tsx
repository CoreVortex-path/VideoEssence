import { useAppStore } from '../store/appStore'
import { formatTime } from '../player/PlayerControls'

interface Bookmark {
  time: number
  text: string
}

// Мок до появления API закладок
const MOCK_BOOKMARKS: Bookmark[] = [
  { time: 0, text: 'Intro: what are transformers' },
  { time: 14, text: 'Attention mechanism explained' },
  { time: 42, text: 'Scaling laws overview' },
  { time: 75, text: 'Emergent capabilities' },
]

/** Read-only список закладок: клик → seek видео. */
export default function BookmarksPanel() {
  const jumpTo = useAppStore((s) => s.jumpTo)

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto p-2">
      {MOCK_BOOKMARKS.map((b) => (
        <button
          key={b.time}
          type="button"
          onClick={() => jumpTo(b.time)}
          className="flex items-center gap-2 rounded-md border border-transparent px-2 py-1.5 text-left transition-colors hover:border-border-glass hover:bg-bg-card"
        >
          <span className="text-[11px] tabular-nums text-amber">
            {formatTime(b.time)}
          </span>
          <span className="truncate text-[12px] text-text-secondary">{b.text}</span>
        </button>
      ))}
    </div>
  )
}
