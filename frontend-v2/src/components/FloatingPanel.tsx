import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { CloseIcon } from '../pdf/icons'

const PANEL_MIN = 320
const PANEL_MAX = 720
const PANEL_DEFAULT = 420
/** Ширина иконочной полоски RightPanel (48px) + отступ 8px. */
const STRIP_OFFSET = 56

interface FloatingPanelProps {
  title: string
  onClose: () => void
  children: ReactNode
}

/**
 * Плавающая glass-панель у правого края (оверлей поверх main, рядом с полоской иконок).
 * Ресайз — drag за левый край, закрытие — кнопка × или Esc.
 */
export default function FloatingPanel({ title, onClose, children }: FloatingPanelProps) {
  const [width, setWidth] = useState(PANEL_DEFAULT)
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null)

  // Esc — закрыть панель
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  // Resize за левый край нативными mouse-событиями (паттерн бывшего startRightDrag)
  const startDrag = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      e.preventDefault()
      dragRef.current = { startX: e.clientX, startWidth: width }

      const onMove = (ev: MouseEvent) => {
        if (!dragRef.current) return
        const delta = dragRef.current.startX - ev.clientX
        const next = dragRef.current.startWidth + delta
        setWidth(Math.min(PANEL_MAX, Math.max(PANEL_MIN, next)))
      }
      const onUp = () => {
        dragRef.current = null
        window.removeEventListener('mousemove', onMove)
        window.removeEventListener('mouseup', onUp)
      }
      window.addEventListener('mousemove', onMove)
      window.addEventListener('mouseup', onUp)
    },
    [width],
  )

  return (
    <div
      className="fixed bottom-2 top-2 z-40 flex flex-col overflow-hidden rounded-md border border-border-glass bg-bg-glass shadow-lg backdrop-blur-md"
      style={{ right: STRIP_OFFSET, width }}
    >
      {/* Drag-хэндл на левом крае */}
      <div
        onMouseDown={startDrag}
        title="Изменить ширину панели"
        className="absolute left-0 top-0 z-10 h-full w-1.5 cursor-ew-resize transition-colors hover:bg-accent/40"
      />

      <div className="flex h-10 shrink-0 items-center justify-between border-b border-border-glass pl-4 pr-2">
        <span className="t-page-title">{title}</span>
        <button
          type="button"
          onClick={onClose}
          title="Закрыть (Esc)"
          className="flex h-7 w-7 items-center justify-center rounded text-text-muted transition-colors hover:bg-bg-card hover:text-text-primary"
        >
          <CloseIcon className="h-4 w-4" />
        </button>
      </div>

      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
    </div>
  )
}
