import { useState } from 'react'
import { Layer, Line, Rect as KRect, Stage } from 'react-konva'
import type { KonvaEventObject } from 'konva/lib/Node'
import type { PageViewport } from 'pdfjs-dist'
import { newAnnotationId, usePdfStore } from './pdfStore'
import type { Annotation, PdfRect, PdfTool } from './types'
import { pdfRectToViewport, pdfPointToPymupdf, viewportPointToPdf } from './coords'

const HIGHLIGHT_COLOR = '#facc15'
const PEN_COLOR = '#ef4444'
const RECT_COLOR = '#60a5fa'

interface DraftState {
  tool: 'highlight' | 'underline' | 'rect' | 'pen'
  start: [number, number]
  current: [number, number]
  points: number[]
}

function dragRect(start: [number, number], current: [number, number]): PdfRect {
  return {
    x0: Math.min(start[0], current[0]),
    y0: Math.min(start[1], current[1]),
    x1: Math.max(start[0], current[0]),
    y1: Math.max(start[1], current[1]),
  }
}

/** Single annotation renderer — new types get a case here, not in the viewer. */
function AnnotationShape({
  annotation,
  viewport,
  erasable,
}: {
  annotation: Annotation
  viewport: PageViewport
  erasable: boolean
}) {
  const removeAnnotation = usePdfStore((s) => s.removeAnnotation)
  const onClick = erasable ? () => removeAnnotation(annotation.id) : undefined

  switch (annotation.type) {
    case 'highlight':
      return (
        <>
          {annotation.rects.map((rect, i) => {
            const r = pdfRectToViewport(viewport, rect)
            return (
              <KRect
                key={i}
                x={r.left}
                y={r.top}
                width={r.width}
                height={r.height}
                fill={HIGHLIGHT_COLOR}
                opacity={0.35}
                listening={erasable}
                onClick={onClick}
                onTap={onClick}
              />
            )
          })}
        </>
      )
    case 'underline':
      return (
        <>
          {annotation.rects.map((rect, i) => {
            const r = pdfRectToViewport(viewport, rect)
            const y = r.top + r.height - 1
            return (
              <Line
                key={i}
                points={[r.left, y, r.left + r.width, y]}
                stroke={HIGHLIGHT_COLOR}
                strokeWidth={1.6}
                listening={erasable}
                onClick={onClick}
                onTap={onClick}
                hitStrokeWidth={8}
              />
            )
          })}
        </>
      )
    case 'pen': {
      const px: number[] = []
      for (let i = 0; i < annotation.points.length; i += 2) {
        const [x, y] = viewport.convertToViewportPoint(
          annotation.points[i],
          annotation.points[i + 1],
        ) as [number, number]
        px.push(x, y)
      }
      return (
        <Line
          points={px}
          stroke={PEN_COLOR}
          strokeWidth={2}
          lineCap="round"
          lineJoin="round"
          tension={0.4}
          listening={erasable}
          onClick={onClick}
          onTap={onClick}
          hitStrokeWidth={10}
        />
      )
    }
    case 'rect': {
      const r = pdfRectToViewport(viewport, annotation.rect)
      return (
        <KRect
          x={r.left}
          y={r.top}
          width={r.width}
          height={r.height}
          stroke={RECT_COLOR}
          strokeWidth={1.6}
          listening={erasable}
          onClick={onClick}
          onTap={onClick}
        />
      )
    }
    case 'note':
      // Note markers are HTML elements (see PdfPage) so they stay clickable
      // in select mode; nothing to draw on the Konva layer.
      return null
  }
}

function DraftShape({ draft, viewport }: { draft: DraftState; viewport: PageViewport }) {
  if (draft.tool === 'pen') {
    const px: number[] = []
    for (let i = 0; i < draft.points.length; i += 2) {
      const [x, y] = viewport.convertToViewportPoint(
        draft.points[i],
        draft.points[i + 1],
      ) as [number, number]
      px.push(x, y)
    }
    return (
      <Line
        points={px}
        stroke={PEN_COLOR}
        strokeWidth={2}
        lineCap="round"
        lineJoin="round"
        tension={0.4}
        listening={false}
      />
    )
  }
  const r = pdfRectToViewport(viewport, dragRect(draft.start, draft.current))
  if (draft.tool === 'rect') {
    return (
      <KRect
        x={r.left}
        y={r.top}
        width={r.width}
        height={r.height}
        stroke={RECT_COLOR}
        strokeWidth={1.6}
        listening={false}
      />
    )
  }
  return (
    <KRect
      x={r.left}
      y={r.top}
      width={r.width}
      height={r.height}
      fill={HIGHLIGHT_COLOR}
      opacity={0.35}
      listening={false}
    />
  )
}

interface AnnotationOverlayProps {
  pageNumber: number
  viewport: PageViewport
  tool: PdfTool
  annotations: Annotation[]
}

/**
 * Konva overlay for user annotations. The PDF itself is rendered on a plain
 * canvas; this stage only hosts annotation shapes and drawing input.
 * Shapes are stored in PDF points and converted with the current viewport.
 */
export default function AnnotationOverlay({
  pageNumber,
  viewport,
  tool,
  annotations,
}: AnnotationOverlayProps) {
  const addAnnotation = usePdfStore((s) => s.addAnnotation)
  const setNoteDraft = usePdfStore((s) => s.setNoteDraft)
  const [draft, setDraft] = useState<DraftState | null>(null)

  const drawing =
    tool === 'highlight' || tool === 'underline' || tool === 'pen' || tool === 'rect'

  const toPdf = (e: KonvaEventObject<MouseEvent | TouchEvent>): [number, number] | null => {
    const stage = e.target.getStage()
    const pos = stage?.getPointerPosition()
    if (!pos) return null
    return viewportPointToPdf(viewport, pos.x, pos.y)
  }

  const onMouseDown = (e: KonvaEventObject<MouseEvent>) => {
    const pt = toPdf(e)
    if (!pt) return
    if (drawing) {
      setDraft({ tool, start: pt, current: pt, points: [...pt] })
    }
  }

  const onMouseMove = (e: KonvaEventObject<MouseEvent>) => {
    if (!draft) return
    const pt = toPdf(e)
    if (!pt) return
    setDraft((d) =>
      d
        ? {
            ...d,
            current: pt,
            points: d.tool === 'pen' ? [...d.points, ...pt] : d.points,
          }
        : d,
    )
  }

  const onMouseUp = (e: KonvaEventObject<MouseEvent>) => {
    const pt = toPdf(e)
    if (tool === 'note') {
      if (pt) {
        // Note anchors are stored in locator space (top-left origin) —
        // the note itself is created via the backend notes API.
        const [ax, ay] = pdfPointToPymupdf(viewport, pt[0], pt[1])
        setNoteDraft({ page: pageNumber, x: ax, y: ay })
      }
      return
    }
    if (!draft || !pt) return
    setDraft(null)

    if (draft.tool === 'pen') {
      if (draft.points.length >= 4) {
        addAnnotation({
          id: newAnnotationId(),
          type: 'pen',
          page: pageNumber,
          points: draft.points,
        })
      }
      return
    }

    const rect = dragRect(draft.start, pt)
    if (rect.x1 - rect.x0 < 2 || rect.y1 - rect.y0 < 2) return
    if (draft.tool === 'rect') {
      addAnnotation({ id: newAnnotationId(), type: 'rect', page: pageNumber, rect })
    } else if (draft.tool === 'highlight') {
      addAnnotation({ id: newAnnotationId(), type: 'highlight', page: pageNumber, rects: [rect] })
    } else {
      addAnnotation({ id: newAnnotationId(), type: 'underline', page: pageNumber, rects: [rect] })
    }
  }

  return (
    <Stage
      width={viewport.width}
      height={viewport.height}
      style={{
        position: 'absolute',
        inset: 0,
        zIndex: 3,
        pointerEvents: tool === 'select' || tool === 'hand' ? 'none' : 'auto',
        cursor: tool === 'eraser' ? 'cell' : drawing ? 'crosshair' : 'default',
      }}
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
    >
      <Layer listening={tool === 'eraser'}>
        {annotations.map((a) => (
          <AnnotationShape
            key={a.id}
            annotation={a}
            viewport={viewport}
            erasable={tool === 'eraser' && a.type !== 'note'}
          />
        ))}
        {draft && <DraftShape draft={draft} viewport={viewport} />}
      </Layer>
    </Stage>
  )
}
