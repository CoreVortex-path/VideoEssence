import { useAppStore } from '../store/appStore'
import ChapterNav from './ChapterNav'

const SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2]

export function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export default function PlayerControls() {
  const playerTime = useAppStore((s) => s.playerTime)
  const duration = useAppStore((s) => s.duration)
  const isPlaying = useAppStore((s) => s.isPlaying)
  const playbackRate = useAppStore((s) => s.playbackRate)
  const togglePlay = useAppStore((s) => s.togglePlay)
  const setPlaybackRate = useAppStore((s) => s.setPlaybackRate)

  const requestFullscreen = () => {
    document.querySelector('video')?.requestFullscreen?.()
  }

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-bg-panel border-t border-border">
      {/* Лево: play + время */}
      <button
        type="button"
        onClick={togglePlay}
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-text-primary hover:bg-bg-card"
      >
        {isPlaying ? '⏸' : '▶'}
      </button>

      <span className="shrink-0 text-[12px] tabular-nums text-text-secondary">
        {formatTime(playerTime)} / {formatTime(duration)}
      </span>

      {/* Центр-лево: название главы (не по центру экрана, а левее) */}
      <div className="ml-6 flex-1 max-w-[320px]">
        <ChapterNav />
      </div>

      <div className="flex-1" />

      {/* Право: скорость + fullscreen */}
      <select
        value={playbackRate}
        onChange={(e) => setPlaybackRate(Number(e.target.value))}
        className="rounded border border-border bg-bg-secondary px-2 py-1 text-[12px] text-text-secondary outline-none"
      >
        {SPEEDS.map((v) => (
          <option key={v} value={v}>{v}x</option>
        ))}
      </select>

      <button
        type="button"
        onClick={requestFullscreen}
        className="flex h-8 w-8 items-center justify-center rounded-md text-text-muted hover:bg-bg-card hover:text-text-primary"
      >
        ⛶
      </button>
    </div>
  )
}