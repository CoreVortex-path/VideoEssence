/** Shared types for the Smart PDF Workspace. */

/** Axis-aligned rect in unscaled PDF points (page space, y grows upward). */
export interface PdfRect {
  x0: number
  y0: number
  x1: number
  y1: number
}

interface AnnotationBase {
  id: string
  /** 1-based page number. */
  page: number
}

export interface HighlightAnnotation extends AnnotationBase {
  type: 'highlight'
  rects: PdfRect[]
}

export interface UnderlineAnnotation extends AnnotationBase {
  type: 'underline'
  rects: PdfRect[]
}

export interface PenAnnotation extends AnnotationBase {
  type: 'pen'
  /** Flat [x1, y1, x2, y2, ...] in PDF points. */
  points: number[]
}

export interface RectAnnotation extends AnnotationBase {
  type: 'rect'
  rect: PdfRect
}

export interface NoteAnnotation extends AnnotationBase {
  type: 'note'
  x: number
  y: number
  /** Backend note id (null until the note is saved via the notes API). */
  noteId: string | null
}

export type Annotation =
  | HighlightAnnotation
  | UnderlineAnnotation
  | PenAnnotation
  | RectAnnotation
  | NoteAnnotation

export type PdfTool =
  | 'select'
  | 'hand'
  | 'highlight'
  | 'underline'
  | 'pen'
  | 'rect'
  | 'note'
  | 'eraser'

export type FitMode = 'width' | 'page' | 'custom'

/** One search hit: char offsets inside the page's extracted text. */
export interface SearchMatch {
  page: number
  start: number
  end: number
}

/** Live text selection inside a page's text layer. */
export interface PdfSelection {
  page: number
  text: string
  rects: PdfRect[]
  /** Anchor for the contextual toolbar, px relative to the page container. */
  anchorX: number
  anchorY: number
  /** Note anchor in locator space (PDF points, top-left origin). */
  noteAnchor: [number, number]
}

/** Inline editor state for a freshly placed note marker. */
export interface NoteDraft {
  page: number
  /** Anchor in locator space: PDF points, origin top-left (PyMuPDF). */
  x: number
  y: number
  selectedText?: string
}
