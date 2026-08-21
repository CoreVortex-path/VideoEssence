import { useEffect, useRef, useState } from 'react'
import type { PDFDocumentProxy } from 'pdfjs-dist'
import { usePdfStore } from './pdfStore'

const THUMB_WIDTH = 120

interface OutlineNode {
  title: string
  dest: string | unknown[] | null
  items: OutlineNode[]
}

function Thumbnail({ doc, pageNumber }: { doc: PDFDocumentProxy; pageNumber: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const rotation = usePdfStore((s) => s.rotation)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setVisible(true)
          observer.disconnect()
        }
      },
      { rootMargin: '200px 0px' },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!visible) return
    let cancelled = false
    doc.getPage(pageNumber).then(async (page) => {
      if (cancelled) return
      const base = page.getViewport({ scale: 1, rotation })
      const scale = THUMB_WIDTH / base.width
      const viewport = page.getViewport({ scale, rotation })
      const canvas = canvasRef.current
      if (!canvas) return
      canvas.width = Math.floor(viewport.width)
      canvas.height = Math.floor(viewport.height)
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      await page.render({ canvasContext: ctx, canvas, viewport }).promise.catch(() => undefined)
    })
    return () => {
      cancelled = true
    }
  }, [doc, pageNumber, visible, rotation])

  return (
    <div ref={wrapRef} className="flex min-h-[80px] items-center justify-center">
      <canvas ref={canvasRef} className="block bg-white" />
    </div>
  )
}

function OutlineItem({
  node,
  depth,
  onNavigate,
}: {
  node: OutlineNode
  depth: number
  onNavigate: (dest: string | unknown[] | null) => void
}) {
  return (
    <div>
      <button
        type="button"
        onClick={() => onNavigate(node.dest)}
        className="block w-full truncate rounded px-2 py-1 text-left text-[12px] text-text-secondary transition-colors hover:bg-bg-card hover:text-text-primary"
        style={{ paddingLeft: 8 + depth * 12 }}
        title={node.title}
      >
        {node.title}
      </button>
      {node.items.map((child, i) => (
        <OutlineItem key={i} node={child} depth={depth + 1} onNavigate={onNavigate} />
      ))}
    </div>
  )
}

/** Left column: page thumbnails, switchable to the document outline. */
export default function ThumbnailsPanel({ doc }: { doc: PDFDocumentProxy }) {
  const numPages = usePdfStore((s) => s.numPages)
  const currentPage = usePdfStore((s) => s.currentPage)
  const requestScrollTo = usePdfStore((s) => s.requestScrollTo)

  const [tab, setTab] = useState<'pages' | 'outline'>('pages')
  const [outline, setOutline] = useState<OutlineNode[] | null>(null)
  const listRef = useRef<HTMLDivElement>(null)

  // Load outline lazily on first switch.
  useEffect(() => {
    if (tab !== 'outline' || outline !== null) return
    let cancelled = false
    doc.getOutline().then((items) => {
      if (!cancelled) setOutline((items as OutlineNode[] | null) ?? [])
    })
    return () => {
      cancelled = true
    }
  }, [tab, outline, doc])

  // Keep the current thumbnail in view.
  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-thumb="${currentPage}"]`)
    el?.scrollIntoView({ block: 'nearest' })
  }, [currentPage])

  const navigate = async (dest: string | unknown[] | null) => {
    try {
      const resolved =
        typeof dest === 'string' ? ((await doc.getDestination(dest)) as unknown[] | null) : dest
      const ref = Array.isArray(resolved) ? resolved[0] : null
      if (!ref) return
      const index = await doc.getPageIndex(ref as Parameters<typeof doc.getPageIndex>[0])
      requestScrollTo(index + 1)
    } catch {
      /* битый dest — игнорируем */
    }
  }

  return (
    <div className="flex h-full w-[152px] shrink-0 flex-col border-r border-border-glass bg-bg-secondary">
      <div className="flex shrink-0 border-b border-border-glass">
        {(['pages', 'outline'] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`flex-1 px-2 py-1.5 text-[11px] transition-colors ${
              tab === t
                ? 'border-b-2 border-accent text-text-primary'
                : 'text-text-muted hover:text-text-secondary'
            }`}
          >
            {t === 'pages' ? 'Pages' : 'Outline'}
          </button>
        ))}
      </div>

      <div ref={listRef} className="min-h-0 flex-1 overflow-y-auto p-2">
        {tab === 'pages' ? (
          <div className="flex flex-col gap-2">
            {Array.from({ length: numPages }, (_, i) => i + 1).map((n) => (
              <button
                key={n}
                type="button"
                data-thumb={n}
                onClick={() => requestScrollTo(n)}
                className={`flex flex-col items-center gap-1 rounded-md border p-1.5 transition-colors ${
                  n === currentPage
                    ? 'border-accent bg-accent/10'
                    : 'border-border-glass hover:border-text-faint'
                }`}
              >
                <Thumbnail doc={doc} pageNumber={n} />
                <span
                  className={`text-[10px] ${n === currentPage ? 'text-accent' : 'text-text-faint'}`}
                >
                  {n}
                </span>
              </button>
            ))}
          </div>
        ) : outline === null ? (
          <div className="px-2 py-4 text-center text-[11px] text-text-faint">Loading…</div>
        ) : outline.length === 0 ? (
          <div className="px-2 py-4 text-center text-[11px] text-text-faint">
            No outline in this document
          </div>
        ) : (
          outline.map((node, i) => (
            <OutlineItem key={i} node={node} depth={0} onNavigate={navigate} />
          ))
        )}
      </div>
    </div>
  )
}
