import { useState, useRef, useEffect } from 'react'
import { useAppStore } from '../store/appStore'
import { formatTime } from './PlayerControls'

function findCurrentChapterIndex(
  chapters: { start: number }[],
  time: number,
): number {
  if (chapters.length === 0) return -1
  for (let i = chapters.length - 1; i >= 0; i--) {
    if (time >= chapters[i].start) return i
  }
  return 0
}

export default function ChapterNav() {
  const chapters = useAppStore((s) => s.currentTask?.chapters ?? [])
  const playerTime = useAppStore((s) => s.playerTime)
  const jumpTo = useAppStore((s) => s.jumpTo)

  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const currentIdx = findCurrentChapterIndex(chapters, playerTime)
  const current = chapters[currentIdx]

  useEffect(() => {
    if (!open) return
    const handle = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open])

  if (chapters.length === 0) return null

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 rounded-md border border-border-primary bg-[#15121c]/95 px-2 py-1 text-[13px] text-text-secondary transition-colors hover:text-text-primary"
      >
        <span className="text-[10px] text-accent">▸</span>
        <span className="truncate max-w-[260px]">{current?.title ?? '—'}</span>
        <span className="text-[10px] text-text-muted">▾</span>
      </button>

      {open && (
        <div className="absolute bottom-full left-0 z-50 mb-1 max-h-[240px] w-[300px] overflow-y-auto rounded-lg border border-border-primary bg-[#15121c]/95 py-1 shadow-lg backdrop-blur-sm">
          <div className="px-3 py-1 text-[11px] uppercase tracking-wide text-text-muted">
            Chapters · {chapters.length}
          </div>
          {chapters.map((ch, i) => (
            <button
              key={`${ch.title}-${ch.start}`}
              onClick={() => {
                jumpTo(ch.start)
                setOpen(false)
              }}
              className={`t-body flex w-full items-center gap-2 px-3 py-2 text-left transition-colors ${
                i === currentIdx
                  ? 'text-accent bg-accent/10'
                  : 'text-text-secondary hover:bg-bg-card hover:text-text-primary'
              }`}
            >
              <span className="t-meta shrink-0 font-mono text-text-muted">
                {formatTime(ch.start)}
              </span>
              <span className="truncate">{ch.title}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}