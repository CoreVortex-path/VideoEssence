import { useMemo } from 'react'

export interface SelectionOverlayRect {
  left: number
  top: number
  width: number
  height: number
}

export interface SelectionCaret {
  left: number
  top: number
  height: number
}

interface SelectionOverlayProps {
  rects: SelectionOverlayRect[]
  /** Собственная каретка (focus-конец selection) — браузер не рисует caret
   *  в не-editable text layer. */
  caret?: SelectionCaret | null
}

/**
 * Own selection highlight. Pointer-events are disabled so the transparent
 * native pdf.js text layer remains the interaction surface.
 */
export default function SelectionOverlay({ rects, caret }: SelectionOverlayProps) {
  const normalized = useMemo(
    () =>
      rects.filter((r) => r.width > 1 && r.height > 1),
    [rects],
  )

  if (normalized.length === 0 && !caret) return null

  return (
    <div
      aria-hidden="true"
      className="absolute inset-0 z-[3] pointer-events-none"
    >
{normalized.map((r, i) => (
  <div
    key={i}
    className="pdf-selection-highlight"
    style={{
      position: 'absolute',
      left: r.left,
      top: r.top,
      width: r.width,
      height: r.height,
      pointerEvents: 'none',
      background: 'rgba(45, 212, 191, 0.28)',
      borderRadius: 1,
      boxSizing: 'border-box',
    }}
  />
))}
      {caret && (
        <div
          className="pdf-selection-caret"
          style={{ left: caret.left, top: caret.top, height: caret.height }}
        />
      )}
    </div>
  )
}
