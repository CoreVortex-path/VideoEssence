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
        className="flex items-center gap-1.5 text-[12px] text-text-dim hover:text-text-primary transition-colors"
      >
        <span className="text-[10px] text-accent">▸</span>
        <span className="truncate max-w-[260px]">{current?.title ?? '—'}</span>
        <span className="text-[10px] text-text-faint">▾</span>
      </button>

      {open && (
        <div className="absolute bottom-full left-0 z-50 mb-1 max-h-[240px] w-[300px] overflow-y-auto rounded-lg border border-border bg-bg-card py-1 shadow-lg">
          <div className="px-3 py-1 text-[10px] uppercase tracking-wide text-text-faint">
            Chapters · {chapters.length}
          </div>
          {chapters.map((ch, i) => (
            <button
              key={`${ch.title}-${ch.start}`}
              onClick={() => {
                jumpTo(ch.start)
                setOpen(false)
              }}
              className={`flex w-full items-center gap-2 px-3 py-1.5 text-left text-[12px] transition-colors ${
                i === currentIdx
                  ? 'text-accent bg-accent/10'
                  : 'text-text-dim hover:bg-bg-panel hover:text-text-primary'
              }`}
            >
              <span className="shrink-0 font-mono text-[11px] text-text-faint">
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