import { useEffect, useState } from 'react'
import { usePdfStore } from './pdfStore'
import {
  FitIcon,
  FullscreenIcon,
  RotateIcon,
  ZoomInIcon,
  ZoomOutIcon,
} from './icons'

const iconBtn =
  'rounded-md p-1.5 text-text-muted transition-colors hover:bg-bg-card hover:text-text-primary'

interface PdfBottomBarProps {
  onToggleFullscreen: () => void
}

/** Compact bottom bar: zoom, page input, fit width, rotate, fullscreen. */
export default function PdfBottomBar({ onToggleFullscreen }: PdfBottomBarProps) {
  const numPages = usePdfStore((s) => s.numPages)
  const currentPage = usePdfStore((s) => s.currentPage)
  const scale = usePdfStore((s) => s.scale)
  const fitMode = usePdfStore((s) => s.fitMode)
  const zoomIn = usePdfStore((s) => s.zoomIn)
  const zoomOut = usePdfStore((s) => s.zoomOut)
  const resetZoom = usePdfStore((s) => s.resetZoom)
  const setFitMode = usePdfStore((s) => s.setFitMode)
  const rotate = usePdfStore((s) => s.rotate)
  const requestScrollTo = usePdfStore((s) => s.requestScrollTo)

  const [pageInput, setPageInput] = useState(String(currentPage))
  useEffect(() => setPageInput(String(currentPage)), [currentPage])

  const submitPage = () => {
    const n = Number.parseInt(pageInput, 10)
    if (Number.isFinite(n)) requestScrollTo(n)
    else setPageInput(String(currentPage))
  }

  return (
    <div className="flex h-10 shrink-0 items-center justify-center gap-1 border-t border-border-glass bg-bg-secondary px-2">
      <button type="button" onClick={zoomOut} title="Zoom out" className={iconBtn}>
        <ZoomOutIcon className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={resetZoom}
        title="Reset to 100%"
        className="min-w-[46px] rounded-md px-1 py-1 text-center text-[12px] text-text-secondary transition-colors hover:bg-bg-card hover:text-text-primary"
      >
        {Math.round(scale * 100)}%
      </button>
      <button type="button" onClick={zoomIn} title="Zoom in" className={iconBtn}>
        <ZoomInIcon className="h-4 w-4" />
      </button>

      <span className="mx-2 h-4 w-px bg-border-glass" />

      <div className="flex items-center gap-1 text-[12px] text-text-secondary">
        <input
          value={pageInput}
          onChange={(e) => setPageInput(e.target.value.replace(/\D/g, ''))}
          onBlur={submitPage}
          onKeyDown={(e) => {
            if (e.key === 'Enter') submitPage()
          }}
          className="w-10 rounded border border-border-glass bg-bg-primary px-1.5 py-0.5 text-center text-[12px] text-text-primary outline-none focus:border-accent"
        />
        <span className="text-text-faint">/ {numPages || '—'}</span>
      </div>

      <span className="mx-2 h-4 w-px bg-border-glass" />

      <button
        type="button"
        onClick={() => setFitMode(fitMode === 'width' ? 'custom' : 'width')}
        title="Fit width"
        className={`${iconBtn} ${fitMode === 'width' ? 'text-accent' : ''}`}
      >
        <FitIcon className="h-4 w-4" />
      </button>
      <button type="button" onClick={rotate} title="Rotate 90°" className={iconBtn}>
        <RotateIcon className="h-4 w-4" />
      </button>
      <button type="button" onClick={onToggleFullscreen} title="Fullscreen" className={iconBtn}>
        <FullscreenIcon className="h-4 w-4" />
      </button>
    </div>
  )
}
