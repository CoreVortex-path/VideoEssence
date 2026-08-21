import { useCallback, useEffect, useRef, useState } from 'react'
import type { PDFDocumentProxy } from 'pdfjs-dist'
import { MAX_SCALE, MIN_SCALE, usePdfStore } from './pdfStore'
import PdfPage from './PdfPage'
import type { PageFallbackSize } from './PdfPage'

const FIT_PADDING = 48

interface PdfViewerProps {
  doc: PDFDocumentProxy
  documentId: string
}

/**
 * Vertical scroll surface with all pages. Tracks the current page via
 * IntersectionObserver, lazily activates pages near the viewport, handles
 * fit modes and hand-tool panning.
 */
export default function PdfViewer({ doc, documentId }: PdfViewerProps) {
  const numPages = usePdfStore((s) => s.numPages)
  const scale = usePdfStore((s) => s.scale)
  const rotation = usePdfStore((s) => s.rotation)
  const fitMode = usePdfStore((s) => s.fitMode)
  const tool = usePdfStore((s) => s.tool)
  const scrollRequest = usePdfStore((s) => s.scrollRequest)
  const setScale = usePdfStore((s) => s.setScale)
  const setCurrentPage = usePdfStore((s) => s.setCurrentPage)
  const clearScrollRequest = usePdfStore((s) => s.clearScrollRequest)

  const containerRef = useRef<HTMLDivElement>(null)
  const [baseSize, setBaseSize] = useState<PageFallbackSize | null>(null)
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 })
  const [activePages, setActivePages] = useState<Set<number>>(() => new Set([1]))

  // Base size of page 1 (scale 1, no extra rotation) for fit + placeholders.
  useEffect(() => {
    let cancelled = false
    doc.getPage(1).then((page) => {
      if (cancelled) return
      const vp = page.getViewport({ scale: 1 })
      setBaseSize({ width: vp.width, height: vp.height })
    })
    return () => {
      cancelled = true
    }
  }, [doc])

  // Container size tracking.
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver(() => {
      setContainerSize({ width: el.clientWidth, height: el.clientHeight })
    })
    ro.observe(el)
    setContainerSize({ width: el.clientWidth, height: el.clientHeight })
    return () => ro.disconnect()
  }, [])

  // Fit modes: derive scale from container + page size.
  useEffect(() => {
    if (fitMode === 'custom' || !baseSize || containerSize.width === 0) return
    const swapped = rotation % 180 !== 0
    const pageW = swapped ? baseSize.height : baseSize.width
    const pageH = swapped ? baseSize.width : baseSize.height
    const fitW = (containerSize.width - FIT_PADDING) / pageW
    const fitH = (containerSize.height - FIT_PADDING) / pageH
    const next = Math.min(
      MAX_SCALE,
      Math.max(MIN_SCALE, fitMode === 'width' ? fitW : Math.min(fitW, fitH)),
    )
    if (Math.abs(next - scale) > 0.005) setScale(next)
    // setScale не трогает fitMode — цикла нет
  }, [fitMode, baseSize, containerSize, rotation, scale, setScale])

  // Current page tracking: whichever page crosses the middle band.
  useEffect(() => {
    const root = containerRef.current
    if (!root) return
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .map((e) => Number((e.target as HTMLElement).dataset.page))
          .filter((n) => Number.isFinite(n))
          .sort((a, b) => a - b)
        if (visible.length > 0) setCurrentPage(visible[0])
      },
      { root, rootMargin: '-45% 0px -45% 0px', threshold: 0 },
    )
    root.querySelectorAll('[data-page]').forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [numPages, setCurrentPage])

  // Lazy activation of pages near the viewport. Страницы, вышедшие из
  // окна (с запасом rootMargin), деактивируются — иначе canvas-буферы
  // всех посещённых страниц копятся в памяти до гигабайт. Размер
  // страницы при этом сохраняется (viewport остаётся загруженным),
  // поэтому скролл не скачет.
  useEffect(() => {
    const root = containerRef.current
    if (!root) return
    const observer = new IntersectionObserver(
      (entries) => {
        const toAdd: number[] = []
        const toRemove: number[] = []
        for (const e of entries) {
          const n = Number((e.target as HTMLElement).dataset.page)
          if (!Number.isFinite(n)) continue
          if (e.isIntersecting) toAdd.push(n)
          else toRemove.push(n)
        }
        if (toAdd.length === 0 && toRemove.length === 0) return
        setActivePages((prev) => {
          const next = new Set(prev)
          toAdd.forEach((n) => next.add(n))
          toRemove.forEach((n) => next.delete(n))
          if (
            next.size === prev.size &&
            [...next].every((n) => prev.has(n))
          ) {
            return prev // ничего не изменилось — не дёргаем рендер
          }
          return next
        })
      },
      { root, rootMargin: '100% 0px', threshold: 0 },
    )
    root.querySelectorAll('[data-page]').forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [numPages])

  // One-shot scroll requests (page input, thumbnails, outline, search).
  useEffect(() => {
    if (scrollRequest == null) return
    const root = containerRef.current
    const target = root?.querySelector(`[data-page="${scrollRequest}"]`)
    if (target) {
      target.scrollIntoView({ block: 'start', behavior: 'auto' })
    }
    clearScrollRequest()
  }, [scrollRequest, clearScrollRequest])

  // Ctrl+wheel zoom (native listener — React wheel events are passive).
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey) return
      e.preventDefault()
      const s = usePdfStore.getState()
      if (e.deltaY < 0) s.zoomIn()
      else s.zoomOut()
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  // Hand tool: drag to scroll.
  const panRef = useRef<{ x: number; y: number; left: number; top: number } | null>(null)
  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (tool !== 'hand') return
      const el = containerRef.current
      if (!el) return
      panRef.current = {
        x: e.clientX,
        y: e.clientY,
        left: el.scrollLeft,
        top: el.scrollTop,
      }
      el.setPointerCapture(e.pointerId)
    },
    [tool],
  )
  const onPointerMove = useCallback((e: React.PointerEvent) => {
    const pan = panRef.current
    const el = containerRef.current
    if (!pan || !el) return
    el.scrollLeft = pan.left - (e.clientX - pan.x)
    el.scrollTop = pan.top - (e.clientY - pan.y)
  }, [])
  const onPointerUp = useCallback(() => {
    panRef.current = null
  }, [])

  const pages = Array.from({ length: numPages }, (_, i) => i + 1)

  return (
    <div
      ref={containerRef}
      className={`min-h-0 flex-1 overflow-auto ${
        tool === 'hand' ? 'cursor-grab active:cursor-grabbing' : ''
      }`}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    >
      <div className="flex min-w-fit flex-col gap-4 px-6 py-6">
        {pages.map((n) => (
          <div key={n} data-page={n} className="shrink-0">
            <PdfPage
              doc={doc}
              documentId={documentId}
              pageNumber={n}
              active={activePages.has(n)}
              fallbackSize={baseSize}
            />
            <div className="mt-1.5 text-center text-[10px] text-text-faint">{n}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
