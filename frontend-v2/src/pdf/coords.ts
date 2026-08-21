import type { PageViewport } from 'pdfjs-dist'
import type { PdfRect } from './types'

/**
 * Coordinate conventions (fixed contract — do not mix!):
 *
 *  - **User space** (pdf.js): unscaled PDF points, origin bottom-left,
 *    y grows upward. Local annotations (highlight/pen/rect/underline) are
 *    stored in this space; PageViewport converts it to CSS pixels for the
 *    current scale + rotation, so zoom/rotate is just a re-render.
 *  - **Locator space** (backend, PyMuPDF): unscaled PDF points, origin
 *    TOP-LEFT, y grows downward. Everything coming from / going to the
 *    backend uses this: formula `bbox`, note `position`. Conversion between
 *    the two is a y-flip inside the page viewBox — use the `pymupdf*`
 *    helpers below and never convert backend coordinates by hand.
 */

/** viewBox = [x0, y0, x1, y1] in user space; the flip is an involution. */
function flipY(viewport: PageViewport, y: number): number {
  const vb = viewport.viewBox as [number, number, number, number]
  return vb[1] + vb[3] - y
}

export function pdfRectToViewport(viewport: PageViewport, rect: PdfRect) {
  const [ax, ay] = viewport.convertToViewportPoint(rect.x0, rect.y0) as [number, number]
  const [bx, by] = viewport.convertToViewportPoint(rect.x1, rect.y1) as [number, number]
  return {
    left: Math.min(ax, bx),
    top: Math.min(ay, by),
    width: Math.abs(bx - ax),
    height: Math.abs(by - ay),
  }
}

export function pdfPointToViewport(
  viewport: PageViewport,
  x: number,
  y: number,
): [number, number] {
  return viewport.convertToViewportPoint(x, y) as [number, number]
}

export function viewportPointToPdf(
  viewport: PageViewport,
  x: number,
  y: number,
): [number, number] {
  return viewport.convertToPdfPoint(x, y) as [number, number]
}

/** DOM client rect (e.g. from Range.getClientRects) -> PDF points. */
export function clientRectToPdfRect(
  viewport: PageViewport,
  clientRect: { left: number; top: number; right: number; bottom: number },
  containerRect: { left: number; top: number },
): PdfRect {
  const x0 = clientRect.left - containerRect.left
  const y0 = clientRect.top - containerRect.top
  const x1 = clientRect.right - containerRect.left
  const y1 = clientRect.bottom - containerRect.top
  const [ax, ay] = viewport.convertToPdfPoint(x0, y0) as [number, number]
  const [bx, by] = viewport.convertToPdfPoint(x1, y1) as [number, number]
  return {
    x0: Math.min(ax, bx),
    y0: Math.min(ay, by),
    x1: Math.max(ax, bx),
    y1: Math.max(ay, by),
  }
}

/** bbox [x0, y0, x1, y1] from the formulas API (locator space) -> PdfRect. */
export function bboxToPdfRect(bbox: number[]): PdfRect {
  const [x0, y0, x1, y1] = bbox
  return { x0, y0, x1, y1 }
}

// --- Locator space (PyMuPDF, top-left origin) <-> viewport -----------------

/** Backend locator point [x, y] (top-left origin) -> CSS px in the viewport. */
export function pymupdfPointToViewport(
  viewport: PageViewport,
  x: number,
  y: number,
): [number, number] {
  return viewport.convertToViewportPoint(x, flipY(viewport, y)) as [number, number]
}

/** Backend locator rect (top-left origin) -> CSS px box in the viewport. */
export function pymupdfRectToViewport(viewport: PageViewport, rect: PdfRect) {
  const [ax, ay] = pymupdfPointToViewport(viewport, rect.x0, rect.y0)
  const [bx, by] = pymupdfPointToViewport(viewport, rect.x1, rect.y1)
  return {
    left: Math.min(ax, bx),
    top: Math.min(ay, by),
    width: Math.abs(bx - ax),
    height: Math.abs(by - ay),
  }
}

/** CSS px in the viewport -> backend locator point [x, y] (top-left origin). */
export function viewportPointToPymupdf(
  viewport: PageViewport,
  x: number,
  y: number,
): [number, number] {
  const [ux, uy] = viewport.convertToPdfPoint(x, y) as [number, number]
  return [ux, flipY(viewport, uy)]
}

/** User-space point (pdf.js) -> backend locator point [x, y] (top-left origin). */
export function pdfPointToPymupdf(
  viewport: PageViewport,
  x: number,
  y: number,
): [number, number] {
  return [x, flipY(viewport, y)]
}
