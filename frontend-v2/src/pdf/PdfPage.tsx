import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { TextLayer } from 'pdfjs-dist'
import type { PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist'
import { usePdfStore } from './pdfStore'
import {
  caretRect,
  domToPos,
  getLogicalSelection,
  useKeyboardSelection,
} from './useKeyboardSelection'
import type { Model } from './useKeyboardSelection'
import AnnotationOverlay from './AnnotationOverlay'
import SelectionToolbar from './SelectionToolbar'
import FormulaPopover from './FormulaPopover'
import { NoteDraftEditor, NoteViewPopover } from './NotePopovers'
import {
  bboxToPdfRect,
  clientRectToPdfRect,
  pdfPointToPymupdf,
  pymupdfPointToViewport,
  pymupdfRectToViewport,
} from './coords'
import { getPageText, matchRects } from './usePageText'
import type { PageText } from './usePageText'
import SelectionOverlay, { type SelectionOverlayRect } from './SelectionOverlay'

export interface PageFallbackSize {
  width: number
  height: number
}

/**
 * Сливает rect'ы одной визуальной строки в один прямоугольник: range
 * getClientRects() отдаёт по rect'у на span, и при наложении полупрозрачных
 * подсветок стыки выглядят темнее («наслаивание»).
 */
/**function mergeLineRects(rects: SelectionOverlayRect[]): SelectionOverlayRect[] {
  const sorted = [...rects].sort((a, b) => a.top - b.top || a.left - b.left)
  const out: SelectionOverlayRect[] = []
  for (const r of sorted) {
    const last = out[out.length - 1]
    if (
      last &&
      Math.abs(last.top - r.top) <= 1 &&
      Math.abs(last.height - r.height) <= 1 &&
      r.left <= last.left + last.width + 1
    ) {
      const right = Math.max(last.left + last.width, r.left + r.width)
      last.width = right - last.left
    } else {
      out.push({ ...r })
    }
  }
  return out
}*/

interface PdfPageProps {
  doc: PDFDocumentProxy
  documentId: string
  pageNumber: number
  /** Render canvas/text layer only when near the viewport. */
  active: boolean
  /** Size of page 1 at scale 1 — placeholder sizing before this page loads. */
  fallbackSize: PageFallbackSize | null
}

/**
 * One PDF page: pdf.js canvas + text layer + Konva annotation overlay +
 * HTML layers (formula regions, note markers, search hits, popovers).
 */
export default function PdfPage({
  doc,
  documentId,
  pageNumber,
  active,
  fallbackSize,
}: PdfPageProps) {
  const scale = usePdfStore((s) => s.scale)
  const rotation = usePdfStore((s) => s.rotation)
  const tool = usePdfStore((s) => s.tool)
  const annotations = usePdfStore((s) => s.annotations[pageNumber])
  const searchMatches = usePdfStore((s) => s.searchMatches)
  const currentMatchIndex = usePdfStore((s) => s.currentMatchIndex)
  const searchOpen = usePdfStore((s) => s.searchOpen)
  const selection = usePdfStore((s) => s.selection)
  const setSelection = usePdfStore((s) => s.setSelection)
  const openFormulaChunkId = usePdfStore((s) => s.openFormulaChunkId)
  const setOpenFormulaChunkId = usePdfStore((s) => s.setOpenFormulaChunkId)
  const openNoteId = usePdfStore((s) => s.openNoteId)
  const setOpenNoteId = usePdfStore((s) => s.setOpenNoteId)
  const noteDraft = usePdfStore((s) => s.noteDraft)

  const formulas = usePdfStore((s) => s.formulasByPage[pageNumber])
  const pageNotes = usePdfStore((s) => s.notesByPage[pageNumber])

  const [page, setPage] = useState<PDFPageProxy | null>(null)
  const [pageText, setPageText] = useState<PageText | null>(null)
  // Увеличивается после каждого завершённого рендера text layer —
  // сигнал keyboard-контроллеру перестроить модель строк.
  const [textLayerVersion, setTextLayerVersion] = useState(0)
  const [selectionClientRects, setSelectionClientRects] = useState<SelectionOverlayRect[]>([])
  // Собственная каретка (в координатах контейнера страницы): браузер не
  // рисует caret в не-editable text layer, caret-color там не работает.
  const [selectionCaret, setSelectionCaret] = useState<{
    left: number
    top: number
    height: number
  } | null>(null)

  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const textLayerRef = useRef<HTMLDivElement>(null)
  // Модель строк/колонок текущего рендера text layer — заполняет
  // useKeyboardSelection, читает captureSelection.
  const selectionModelRef = useRef<Model | null>(null)

  useEffect(() => {
    let cancelled = false
    doc.getPage(pageNumber).then((p) => {
      if (!cancelled) setPage(p)
    })
    return () => {
      cancelled = true
    }
  }, [doc, pageNumber])

  // CSS-pixel viewport (layout, text layer, overlays).
  const viewport = useMemo(
    () => (page ? page.getViewport({ scale, rotation }) : null),
    [page, scale, rotation],
  )

  // --- Canvas render (device pixels, capped DPR) ---
  // Рендеры на одном canvas строго последовательны: новый рендер ждёт
  // завершения/отмены предыдущего. Иначе pdf.js бросает "Cannot use the
  // same canvas during multiple render() operations", а страница остаётся
  // частично дорисованной (текст есть, часть картинок пропадает).
  const renderTaskRef = useRef<{ cancel: () => void; promise: Promise<unknown> } | null>(null)
  useEffect(() => {
    const canvas = canvasRef.current
    if (!page || !viewport || !canvas || !active) return
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const renderViewport = page.getViewport({ scale: scale * dpr, rotation })
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let disposed = false
    let task: { cancel: () => void; promise: Promise<unknown> } | null = null

    const run = async () => {
      const prev = renderTaskRef.current
      if (prev) {
        prev.cancel()
        try {
          await prev.promise
        } catch {
          /* отмена предыдущего рендера — штатная ситуация */
        }
      }
      if (disposed) return
      canvas.width = Math.floor(renderViewport.width)
      canvas.height = Math.floor(renderViewport.height)
      canvas.style.width = `${Math.floor(viewport.width)}px`
      canvas.style.height = `${Math.floor(viewport.height)}px`
      task = page.render({ canvasContext: ctx, canvas, viewport: renderViewport })
      renderTaskRef.current = task
      try {
        await task.promise
      } catch (err) {
        // RenderingCancelledException — нормально; остальное не глотаем.
        if (err && typeof err === 'object' && 'name' in err && err.name === 'RenderingCancelledException') {
          return
        }
        console.warn(`[pdf] render failed on page ${pageNumber}:`, err)
      } finally {
        if (renderTaskRef.current === task) renderTaskRef.current = null
      }
    }
    void run()

    return () => {
      disposed = true
      task?.cancel()
    }
  }, [page, viewport, scale, rotation, active, pageNumber])

  // Деактивация страницы: освобождаем bitmap canvas. Буфер
  // (width × height × 4 байта, ещё ×DPR²) — основная стоимость страницы
  // в памяти; cancel рендера сам по себе буфер не освобождает.
  useEffect(() => {
    if (active) return
    const canvas = canvasRef.current
    if (canvas) {
      canvas.width = 0
      canvas.height = 0
    }
    const textLayer = textLayerRef.current
    if (textLayer) textLayer.innerHTML = ''
  }, [active])

  // --- Text layer (selection + search) ---
  // Ровно ОДИН TextLayer на контейнер: рендер идёт асинхронно чанками,
  // поэтому второй инстанс на том же контейнере перемешивает свои спаны
  // с чужими (ломает выделение и удваивает DOM).
  useEffect(() => {
    const container = textLayerRef.current
    if (!page || !viewport || !container || !active) return
    container.innerHTML = ''
    setSelectionClientRects([])

    // КРИТИЧНО: в pdf.js 6 размеры текстового слоя считаются через
    // --total-scale-factor / --scale-round-*, которые pdf_viewer.css
    // определяет только на `.pdfViewer .page` — у нас этих классов нет,
    // поэтому выставляем переменные сами. Без них font-size спанов
    // инвалиден и прямоугольники выделения не совпадают с глифами.
    container.style.setProperty('--scale-factor', scale.toString())
    container.style.setProperty('--total-scale-factor', scale.toString())
    container.style.setProperty('--scale-round-x', '1px')
    container.style.setProperty('--scale-round-y', '1px')

    const textLayer = new TextLayer({
      textContentSource: page.streamTextContent(),
      container,
      viewport, // CSS-пиксельный viewport (тот же, что для layout)
    })

    let cancelled = false

    const render = async () => {
      try {
        await textLayer.render()
        if (cancelled) return
        // Маркер конца контента: без него drag-выделение за пределы
        // последней строки прыгает в конец документа.
        const end = document.createElement('div')
        end.className = 'endOfContent'
        container.append(end)
        setTextLayerVersion((v) => v + 1)
      } catch {
        // отмена рендера — штатная ситуация
      }
    }
    void render()

    return () => {
      cancelled = true
      textLayer.cancel()
    }
  }, [page, viewport, active, scale])

  // --- Text selection capture (select tool only) ---
  // Native DOM selection is used only as the input mechanism. The actual
  // selection text/geometry comes from our logical line/column model.
const computeOverlayRects = useCallback((): SelectionOverlayRect[] => {
  const container = textLayerRef.current
  const model = selectionModelRef.current

  if (!container || !model) return []

  const logical = getLogicalSelection(model, container)

  if (!logical) return []

  const containerRect = container.getBoundingClientRect()

  return logical.clientRects
    .map((r) => ({
      left: r.left - containerRect.left,
      top: r.top - containerRect.top,
      width: r.width,
      height: r.height,
    }))
    .filter((r) => r.width > 1 && r.height > 1)
}, [])

  const updateOverlay = useCallback(() => {
    setSelectionClientRects(computeOverlayRects())
  }, [computeOverlayRects])

  const captureSelection = useCallback(() => {
    const container = textLayerRef.current
    const model = selectionModelRef.current
    if (!container || !model || !viewport) return

    const logical = getLogicalSelection(model, container)
    if (!logical) return

    const text = logical.text.trim()
    if (!text) return

    const rects = computeOverlayRects()
    if (rects.length === 0) return

    const containerRect = container.getBoundingClientRect()
    const pdfRects = rects.map((r) =>
      clientRectToPdfRect(
        viewport,
        new DOMRect(
          containerRect.left + r.left,
          containerRect.top + r.top,
          r.width,
          r.height,
        ),
        containerRect,
      ),
    )

    const firstPdf = pdfRects[0]
    setSelectionClientRects(rects)

    setSelection({
      page: pageNumber,
      text,
      rects: pdfRects,
      anchorX: Math.max(0, rects[0].left),
      anchorY: Math.max(0, rects[0].top - 34),
      // Якорь заметки — начало логического выделения, в locator space.
      noteAnchor: pdfPointToPymupdf(viewport, firstPdf.x0, firstPdf.y1),
    })
  }, [viewport, pageNumber, setSelection, computeOverlayRects])



  // Live-подсветка во время drag: native ::selection скрыт, поэтому overlay
  // обновляется по selectionchange (throttle через rAF). В store выделение
  // попадает только на mouseup — иначе тулбар дёргался бы за мышью.
  useEffect(() => {
    if (tool !== 'select') return
    let raf = 0
    const onSelectionChange = () => {
      if (raf) return
      raf = requestAnimationFrame(() => {
        raf = 0
        const container = textLayerRef.current
        const sel = window.getSelection()
        if (!container || !sel || sel.rangeCount === 0) {
          // Selection снят (Esc, клик вне текста) — гасим overlay и каретку.
          setSelectionClientRects([])
          setSelectionCaret(null)
          return
        }
        const anchorNode = sel.anchorNode
        // Выделение ушло с этой страницы — гасим overlay и каретку.
        if (!anchorNode || !container.contains(anchorNode)) {
          setSelectionClientRects([])
          setSelectionCaret(null)
          return
        }
        updateOverlay()
        // Каретка на focus-конце selection (в т.ч. при collapsed — после клика).
        const model = selectionModelRef.current
        const focusPos =
  model &&
  sel.focusNode &&
  container.contains(sel.focusNode)
    ? domToPos(model, sel.focusNode, sel.focusOffset)
    : null

const cr = model && focusPos
  ? caretRect(model, focusPos)
  : null
        if (cr) {
          // caretRect уже в координатах контейнера text layer.
          setSelectionCaret({
            left: Math.round(cr.x),
            top: Math.round(cr.top),
            height: Math.round(cr.height),
          })
        } else {
          setSelectionCaret(null)
        }
      })
    }
    document.addEventListener('selectionchange', onSelectionChange)
    return () => {
      document.removeEventListener('selectionchange', onSelectionChange)
      if (raf) cancelAnimationFrame(raf)
    }
  }, [tool, updateOverlay])

  // Клавиатурное выделение как в VS Code (Shift+стрелки/Home/End, Esc).
  useKeyboardSelection({
    containerRef: textLayerRef,
    tool,
    renderVersion: textLayerVersion,
    modelRef: selectionModelRef,
    onSelectionChange: captureSelection,
    onSelectionCleared: () => {
      setSelection(null)
      setSelectionClientRects([])
      setSelectionCaret(null)
    },
    onMouseUp: captureSelection,
  })

  // --- Search: fetch this page's text only when it has hits ---
  const pageMatches = useMemo(
    () =>
      searchMatches
        .map((m, globalIndex) => ({ ...m, globalIndex }))
        .filter((m) => m.page === pageNumber),
    [searchMatches, pageNumber],
  )

  useEffect(() => {
    if (pageMatches.length === 0) {
      setPageText(null)
      return
    }
    let cancelled = false
    getPageText(doc, pageNumber).then((pt) => {
      if (!cancelled) setPageText(pt)
    })
    return () => {
      cancelled = true
    }
  }, [doc, pageNumber, pageMatches.length, pageMatches])

  // Close floating UI when clicking the page itself.
  const onPageMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('[data-pdf-ui]')) return
    const isTextLayer = (e.target as HTMLElement).closest('.pdf-text-layer')
    if (!isTextLayer && selection) {
      setSelection(null)
      setSelectionClientRects([])
    }
    if (!isTextLayer) setSelectionCaret(null)
    if (!isTextLayer && openFormulaChunkId) setOpenFormulaChunkId(null)
    if (!isTextLayer && openNoteId) setOpenNoteId(null)
   }

  const width = viewport?.width ?? (fallbackSize ? fallbackSize.width * scale : 600)
  const height = viewport?.height ?? (fallbackSize ? fallbackSize.height * scale : 800)

  return (
    <div
      ref={containerRef}
      data-pdf-page={pageNumber}
      className="relative mx-auto bg-white shadow-[0_2px_14px_rgba(0,0,0,0.55)]"
      style={{ width, height }}
      onMouseDown={onPageMouseDown}
    >
      <canvas ref={canvasRef} className="absolute inset-0" />

      {/* Search hits — under the text layer, above the canvas */}
      {searchOpen && viewport && pageText && (
        <div className="absolute inset-0" style={{ zIndex: 1 }}>
          {pageMatches.flatMap((m) =>
            matchRects(pageText, m.start, m.end, viewport).map((r, i) => (
              <div
                key={`${m.globalIndex}-${i}`}
                className={`pdf-search-highlight ${
                  m.globalIndex === currentMatchIndex ? 'active' : ''
                }`}
                style={{ left: r.left, top: r.top, width: r.width, height: r.height }}
              />
            )),
          )}
        </div>
      )}

      {tool === 'select' && (selectionClientRects.length > 0 || selectionCaret) && (
        <SelectionOverlay rects={selectionClientRects} caret={selectionCaret} />
      )}

      <div
        ref={textLayerRef}
        className="textLayer pdf-text-layer"
        tabIndex={0}
        style={{ pointerEvents: tool === 'select' ? 'auto' : 'none', outline: 'none' }}
      />

      {viewport && (
        <AnnotationOverlay
          pageNumber={pageNumber}
          viewport={viewport}
          tool={tool}
          annotations={annotations ?? []}
        />
      )}

      {/* Formula regions (HTML layer — clickable even in select mode) */}
      {viewport &&
        (formulas ?? []).map((f) => {
          if (!f.bbox) return null
          const r = pymupdfRectToViewport(viewport, bboxToPdfRect(f.bbox))
          const open = openFormulaChunkId === f.chunk_id
          return (
            <div key={f.chunk_id}>
              <div
                className={`pdf-formula-region ${open ? 'open' : ''}`}
                style={{ left: r.left, top: r.top, width: r.width, height: r.height }}
                onMouseDown={(e) => e.stopPropagation()}
                onClick={() => setOpenFormulaChunkId(open ? null : f.chunk_id)}
                title="Formula"
              />
              {open && (
                <div
                  data-pdf-ui
                  className="absolute z-10"
                  style={{
                    left: Math.min(r.left, Math.max(0, viewport.width - 270)),
                    top: r.top + r.height + 6,
                  }}
                >
                  <FormulaPopover documentId={documentId} formula={f} />
                </div>
              )}
            </div>
          )
        })}

      {/* Note markers (backend notes with a page anchor, locator space) */}
      {viewport &&
        (pageNotes ?? []).map((n) => {
          const [x, y] = pymupdfPointToViewport(viewport, n.position![0], n.position![1])
          const open = openNoteId === n.id
          return (
            <div key={n.id}>
              <div
                className="pdf-note-marker"
                style={{ left: x, top: y }}
                onMouseDown={(e) => e.stopPropagation()}
                onClick={() => setOpenNoteId(open ? null : n.id)}
                title={n.tag ? `Note · ${n.tag}` : 'Note'}
              >
                ✎
              </div>
              {open && (
                <div
                  data-pdf-ui
                  className="absolute z-10"
                  style={{ left: Math.min(x + 12, Math.max(0, viewport.width - 250)), top: y }}
                >
                  <NoteViewPopover documentId={documentId} noteId={n.id} />
                </div>
              )}
            </div>
          )
        })}

      {/* Inline editor for a freshly placed note */}
      {viewport && noteDraft && noteDraft.page === pageNumber && (
        <div
          data-pdf-ui
          className="absolute z-10"
          style={(() => {
            const [x, y] = pymupdfPointToViewport(viewport, noteDraft.x, noteDraft.y)
            return { left: Math.min(x + 12, Math.max(0, viewport.width - 250)), top: y }
          })()}
        >
          <NoteDraftEditor documentId={documentId} />
        </div>
      )}

      {/* Selection toolbar */}
      {selection && selection.page === pageNumber && (
        <div
          data-pdf-ui
          className="absolute z-10"
          style={{ left: selection.anchorX, top: selection.anchorY }}
        >
          <SelectionToolbar />
        </div>
      )}
    </div>
  )
}