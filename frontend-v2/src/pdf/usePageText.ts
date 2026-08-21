import { Util } from 'pdfjs-dist'
import type { PageViewport, PDFDocumentProxy } from 'pdfjs-dist'

/** One text run of a page, kept for search-hit geometry. */
export interface PageTextItem {
  str: string
  transform: number[]
  /** Width in unscaled PDF points. */
  width: number
}

export interface PageText {
  items: PageTextItem[]
  /** Concatenated page text (items joined with '\n'). */
  text: string
  /** offsets[i] = char index where items[i].str starts inside `text`. */
  offsets: number[]
}

const cache = new WeakMap<PDFDocumentProxy, Map<number, Promise<PageText>>>()

/** Lazily extract and cache text content per page (for search). */
export function getPageText(doc: PDFDocumentProxy, pageNumber: number): Promise<PageText> {
  let pages = cache.get(doc)
  if (!pages) {
    pages = new Map()
    cache.set(doc, pages)
  }
  let entry = pages.get(pageNumber)
  if (!entry) {
    entry = doc.getPage(pageNumber).then(async (page) => {
      const content = await page.getTextContent()
      const items: PageTextItem[] = []
      const offsets: number[] = []
      let text = ''
      for (const raw of content.items) {
        if (!('str' in raw) || raw.str.length === 0) continue
        offsets.push(text.length)
        items.push({
          str: raw.str,
          transform: raw.transform as number[],
          width: raw.width,
        })
        text += raw.str + '\n'
      }
      return { items, text, offsets }
    })
    pages.set(pageNumber, entry)
  }
  return entry
}

export interface ViewportRect {
  left: number
  top: number
  width: number
  height: number
}

/**
 * Viewport (CSS px) rects covering chars [start, end) of the page text.
 * Approximates partial-item spans linearly along the item's advance vector,
 * so it stays correct under 90° page rotation.
 */
export function matchRects(
  pageText: PageText,
  start: number,
  end: number,
  viewport: PageViewport,
): ViewportRect[] {
  const rects: ViewportRect[] = []
  for (let i = 0; i < pageText.items.length; i++) {
    const item = pageText.items[i]
    const itemStart = pageText.offsets[i]
    const itemEnd = itemStart + item.str.length
    if (itemEnd <= start || itemStart >= end) continue

    const tx = Util.transform(viewport.transform, item.transform) as number[]
    const fontHeight = Math.hypot(tx[2], tx[3])
    const advance = Math.hypot(tx[0], tx[1]) || 1
    const ux = tx[0] / advance
    const uy = tx[1] / advance
    // Height vector (perpendicular to advance, points "up" in device space).
    const vx = fontHeight > 0 ? tx[2] / fontHeight : 0
    const vy = fontHeight > 0 ? tx[3] / fontHeight : -1
    const totalWidth = item.width * viewport.scale

    const frac0 = Math.max(0, start - itemStart) / item.str.length
    const frac1 = (Math.min(itemEnd, end) - itemStart) / item.str.length

    const x0 = tx[4] + ux * frac0 * totalWidth
    const y0 = tx[5] + uy * frac0 * totalWidth
    const x1 = tx[4] + ux * frac1 * totalWidth
    const y1 = tx[5] + uy * frac1 * totalWidth

    const left = Math.min(x0, x1, x0 + vx * fontHeight, x1 + vx * fontHeight)
    const top = Math.min(y0, y1, y0 + vy * fontHeight, y1 + vy * fontHeight)
    const right = Math.max(x0, x1, x0 + vx * fontHeight, x1 + vx * fontHeight)
    const bottom = Math.max(y0, y1, y0 + vy * fontHeight, y1 + vy * fontHeight)
    rects.push({ left, top, width: right - left, height: bottom - top })
  }
  return rects
}
