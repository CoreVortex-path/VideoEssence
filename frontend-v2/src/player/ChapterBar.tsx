import { useAppStore } from '../store/appStore'
import { formatTime } from './PlayerControls'

/** Панель глав из реальных данных задачи: клик → seek, активная по playerTime. */
export default function ChapterBar() {
  const playerTime = useAppStore((s) => s.playerTime)
  const chapters = useAppStore((s) => s.currentTask?.chapters ?? [])
  const jumpTo = useAppStore((s) => s.jumpTo)

  if (chapters.length === 0) return null

  const activeIndex = chapters.reduce((acc, ch, i) => {
    const next = chapters[i + 1]
    return playerTime >= ch.start && (!next || playerTime < next.start) ? i : acc
  }, 0)

  return (
    <div className="flex gap-1 px-3 py-1.5">
      {chapters.map((ch, i) => (
        <button
          key={`${ch.title}-${ch.start}`}
          type="button"
          data-title={`${ch.title} · ${formatTime(ch.start)}`}
          onClick={() => jumpTo(ch.start)}
          className={`chapter-segment relative h-[6px] flex-1 rounded-full transition-all ${
            i === activeIndex ? 'chapter-active' : ''
          }`}
          style={{
            background:
              i === activeIndex
                ? 'linear-gradient(90deg, var(--accent), var(--cyan))'
                : 'var(--border-primary)',
          }}
        />
      ))}
    </div>
  )
}
