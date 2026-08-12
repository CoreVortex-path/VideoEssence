import { useAppStore } from '../store/appStore'

/** Подсказка хоткеев внизу экрана, видна только в zen mode. */
export default function ZenHint() {
  const zenMode = useAppStore((s) => s.zenMode)
  if (!zenMode) return null

  return (
    <div className="glass-panel fixed bottom-4 left-1/2 z-40 -translate-x-1/2 rounded-full border px-4 py-1.5 text-[11px] text-text-muted">
      Press <span className="text-accent">Z</span> to exit Zen Mode ·{' '}
      <span className="text-accent">Space</span> play/pause ·{' '}
      <span className="text-accent">J/L</span> seek
    </div>
  )
}
