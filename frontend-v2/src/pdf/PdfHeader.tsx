import { useEffect, useRef, useState } from 'react'
import { getDocumentMediaUrl } from '../api/client'
import { useAppStore } from '../store/appStore'
import { loadFavorite, saveFavorite, usePdfStore } from './pdfStore'
import {
  BackIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  DotsIcon,
  DownloadIcon,
  FitIcon,
  InfoIcon,
  SearchIcon,
  StarIcon,
  ZoomInIcon,
  ZoomOutIcon,
} from './icons'

interface PdfHeaderProps {
  documentId: string
  onToggleFullscreen: () => void
}

const iconBtn =
  'rounded-md p-1.5 text-text-muted transition-colors hover:bg-bg-card hover:text-text-primary disabled:opacity-30'

export default function PdfHeader({ documentId, onToggleFullscreen }: PdfHeaderProps) {
  const title = useAppStore((s) => s.currentTask?.title) ?? 'Untitled Document'
  const sourceType = useAppStore((s) => s.currentTask?.source_type) ?? 'pdf'
  const setDocumentId = useAppStore((s) => s.setDocumentId)
  const setCurrentTask = useAppStore((s) => s.setCurrentTask)
  const setSourceType = useAppStore((s) => s.setSourceType)

  const numPages = usePdfStore((s) => s.numPages)
  const currentPage = usePdfStore((s) => s.currentPage)
  const scale = usePdfStore((s) => s.scale)
  const fitMode = usePdfStore((s) => s.fitMode)
  const requestScrollTo = usePdfStore((s) => s.requestScrollTo)
  const zoomIn = usePdfStore((s) => s.zoomIn)
  const zoomOut = usePdfStore((s) => s.zoomOut)
  const setFitMode = usePdfStore((s) => s.setFitMode)
  const toggleSearch = usePdfStore((s) => s.toggleSearch)
  const rotate = usePdfStore((s) => s.rotate)

  const [favorite, setFavorite] = useState(() => loadFavorite(documentId))
  const [infoOpen, setInfoOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => setFavorite(loadFavorite(documentId)), [documentId])

  useEffect(() => {
    if (!menuOpen && !infoOpen) return
    const onDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
        setInfoOpen(false)
      }
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [menuOpen, infoOpen])

  const back = () => {
    setDocumentId(null)
    setCurrentTask(null)
    setSourceType(null)
  }

  const toggleFavorite = () => {
    const next = !favorite
    setFavorite(next)
    saveFavorite(documentId, next)
  }

  const cycleFit = () => setFitMode(fitMode === 'width' ? 'page' : 'width')

  return (
    <div className="flex h-11 shrink-0 items-center gap-1 border-b border-border-glass bg-bg-secondary px-2">
      <button type="button" onClick={back} title="Back to library" className={iconBtn}>
        <BackIcon className="h-4 w-4" />
      </button>

      <div className="min-w-0 flex-1 truncate px-1 text-[13px] font-medium text-text-primary">
        {title}
      </div>

      <button
        type="button"
        onClick={toggleFavorite}
        title={favorite ? 'Remove from favorites' : 'Add to favorites'}
        className={`${iconBtn} ${favorite ? 'text-amber hover:text-amber' : ''}`}
      >
        <StarIcon className="h-4 w-4" filled={favorite} />
      </button>

      <div className="mx-1 flex items-center gap-0.5">
        <button
          type="button"
          onClick={() => requestScrollTo(currentPage - 1)}
          disabled={currentPage <= 1}
          title="Previous page"
          className={iconBtn}
        >
          <ChevronLeftIcon className="h-4 w-4" />
        </button>
        <span className="min-w-[52px] text-center text-[12px] text-text-secondary">
          {currentPage}/{numPages || '—'}
        </span>
        <button
          type="button"
          onClick={() => requestScrollTo(currentPage + 1)}
          disabled={numPages > 0 && currentPage >= numPages}
          title="Next page"
          className={iconBtn}
        >
          <ChevronRightIcon className="h-4 w-4" />
        </button>
      </div>

      <div className="mx-1 flex items-center gap-0.5">
        <button type="button" onClick={zoomOut} title="Zoom out" className={iconBtn}>
          <ZoomOutIcon className="h-4 w-4" />
        </button>
        <span className="min-w-[42px] text-center text-[12px] text-text-secondary">
          {Math.round(scale * 100)}%
        </span>
        <button type="button" onClick={zoomIn} title="Zoom in" className={iconBtn}>
          <ZoomInIcon className="h-4 w-4" />
        </button>
      </div>

      <button
        type="button"
        onClick={cycleFit}
        title={fitMode === 'width' ? 'Fit: width (click for fit page)' : 'Fit: page (click for fit width)'}
        className={`${iconBtn} ${fitMode !== 'custom' ? 'text-accent' : ''}`}
      >
        <FitIcon className="h-4 w-4" />
      </button>

      <button type="button" onClick={toggleSearch} title="Search" className={iconBtn}>
        <SearchIcon className="h-4 w-4" />
      </button>

      <div ref={menuRef} className="relative flex items-center">
        <button
          type="button"
          onClick={() => {
            setInfoOpen((v) => !v)
            setMenuOpen(false)
          }}
          title="Document info"
          className={iconBtn}
        >
          <InfoIcon className="h-4 w-4" />
        </button>
        <a
          href={getDocumentMediaUrl(documentId)}
          download
          title="Download PDF"
          className={iconBtn}
        >
          <DownloadIcon className="h-4 w-4" />
        </a>
        <button
          type="button"
          onClick={() => {
            setMenuOpen((v) => !v)
            setInfoOpen(false)
          }}
          title="More"
          className={iconBtn}
        >
          <DotsIcon className="h-4 w-4" />
        </button>

        {infoOpen && (
          <div className="absolute right-0 top-full z-30 mt-1 w-48 rounded-md border border-border-glass bg-bg-glass p-3 text-[12px] text-text-secondary shadow-lg backdrop-blur-md">
            <div className="flex justify-between py-0.5">
              <span className="text-text-faint">Pages</span>
              <span>{numPages || '—'}</span>
            </div>
            <div className="flex justify-between py-0.5">
              <span className="text-text-faint">Source</span>
              <span className="uppercase">{sourceType}</span>
            </div>
          </div>
        )}

        {menuOpen && (
          <div className="absolute right-0 top-full z-30 mt-1 w-40 rounded-md border border-border-glass bg-bg-glass py-1 shadow-lg backdrop-blur-md">
            <button
              type="button"
              onClick={() => {
                onToggleFullscreen()
                setMenuOpen(false)
              }}
              className="block w-full px-3 py-1.5 text-left text-[12px] text-text-secondary hover:bg-bg-card hover:text-text-primary"
            >
              Fullscreen
            </button>
            <button
              type="button"
              onClick={() => {
                rotate()
                setMenuOpen(false)
              }}
              className="block w-full px-3 py-1.5 text-left text-[12px] text-text-secondary hover:bg-bg-card hover:text-text-primary"
            >
              Rotate 90°
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
