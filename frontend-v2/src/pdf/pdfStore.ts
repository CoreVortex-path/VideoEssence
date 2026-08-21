import { create } from 'zustand'
import type { DocumentFormulaItem, NoteResponse } from '../api/client'
import type {
  Annotation,
  FitMode,
  NoteDraft,
  PdfSelection,
  PdfTool,
  SearchMatch,
} from './types'

export const MIN_SCALE = 0.5
export const MAX_SCALE = 3
const ZOOM_STEP = 1.2

function clampScale(scale: number) {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, Math.round(scale * 100) / 100))
}

function annotationsKey(documentId: string) {
  return `ve_pdf_annotations_${documentId}`
}

function loadAnnotations(documentId: string): Record<number, Annotation[]> {
  try {
    const raw = localStorage.getItem(annotationsKey(documentId))
    if (!raw) return {}
    const parsed = JSON.parse(raw) as Record<string, Annotation[]>
    const result: Record<number, Annotation[]> = {}
    for (const [page, list] of Object.entries(parsed)) {
      if (Array.isArray(list)) result[Number(page)] = list
    }
    return result
  } catch {
    return {}
  }
}

function persistAnnotations(
  documentId: string | null,
  annotations: Record<number, Annotation[]>,
) {
  if (!documentId) return
  try {
    localStorage.setItem(annotationsKey(documentId), JSON.stringify(annotations))
  } catch {
    /* localStorage недоступен — аннотации живут только в памяти */
  }
}

interface PdfState {
  documentId: string | null
  numPages: number
  currentPage: number
  scale: number
  fitMode: FitMode
  /** 0 | 90 | 180 | 270, applied on top of the page's own rotation. */
  rotation: number
  tool: PdfTool
  searchOpen: boolean
  searchQuery: string
  searchMatches: SearchMatch[]
  currentMatchIndex: number
  aiPanelOpen: boolean
  pendingPrompt: string | null
  selection: PdfSelection | null
  annotations: Record<number, Annotation[]>
  /** Detected formulas grouped by 1-based page (from the formulas API). */
  formulasByPage: Record<number, DocumentFormulaItem[]>
  /** Backend notes with a page anchor, grouped by 1-based page. */
  notesByPage: Record<number, NoteResponse[]>
  /** Chunk id of the formula whose popover is open. */
  openFormulaChunkId: string | null
  /** Backend note id whose popover is open. */
  openNoteId: string | null
  /** Inline editor for a newly placed note. */
  noteDraft: NoteDraft | null
  /** One-shot scroll request (1-based page), consumed by PdfViewer. */
  scrollRequest: number | null

  reset: (documentId: string) => void
  setNumPages: (numPages: number) => void
  setCurrentPage: (page: number) => void
  setScale: (scale: number) => void
  zoomIn: () => void
  zoomOut: () => void
  resetZoom: () => void
  setFitMode: (mode: FitMode) => void
  rotate: () => void
  setTool: (tool: PdfTool) => void
  toggleSearch: () => void
  setSearchQuery: (query: string) => void
  setSearchMatches: (matches: SearchMatch[]) => void
  setCurrentMatchIndex: (index: number) => void
  stepMatch: (delta: number) => void
  setAiPanelOpen: (open: boolean) => void
  requestPrompt: (prompt: string) => void
  clearPrompt: () => void
  setSelection: (selection: PdfSelection | null) => void
  addAnnotation: (annotation: Annotation) => void
  removeAnnotation: (id: string) => void
  updateAnnotation: (id: string, patch: Partial<Annotation>) => void
  setFormulas: (formulas: DocumentFormulaItem[]) => void
  setNotes: (notes: NoteResponse[]) => void
  setOpenFormulaChunkId: (id: string | null) => void
  setOpenNoteId: (id: string | null) => void
  setNoteDraft: (draft: NoteDraft | null) => void
  requestScrollTo: (page: number) => void
  clearScrollRequest: () => void
}

export const usePdfStore = create<PdfState>((set) => ({
  documentId: null,
  numPages: 0,
  currentPage: 1,
  scale: 1,
  fitMode: 'width',
  rotation: 0,
  tool: 'select',
  searchOpen: false,
  searchQuery: '',
  searchMatches: [],
  currentMatchIndex: 0,
  aiPanelOpen: true,
  pendingPrompt: null,
  selection: null,
  annotations: {},
  formulasByPage: {},
  notesByPage: {},
  openFormulaChunkId: null,
  openNoteId: null,
  noteDraft: null,
  scrollRequest: null,

  reset: (documentId) =>
    set({
      documentId,
      numPages: 0,
      currentPage: 1,
      scale: 1,
      fitMode: 'width',
      rotation: 0,
      tool: 'select',
      searchOpen: false,
      searchQuery: '',
      searchMatches: [],
      currentMatchIndex: 0,
      pendingPrompt: null,
      selection: null,
      annotations: loadAnnotations(documentId),
      formulasByPage: {},
      notesByPage: {},
      openFormulaChunkId: null,
      openNoteId: null,
      noteDraft: null,
      scrollRequest: null,
    }),
  setNumPages: (numPages) => set({ numPages }),
  setCurrentPage: (page) =>
    set((s) => ({ currentPage: Math.min(Math.max(1, page), Math.max(1, s.numPages)) })),
  setScale: (scale) => set({ scale: clampScale(scale) }),
  zoomIn: () => set((s) => ({ scale: clampScale(s.scale * ZOOM_STEP), fitMode: 'custom' })),
  zoomOut: () => set((s) => ({ scale: clampScale(s.scale / ZOOM_STEP), fitMode: 'custom' })),
  resetZoom: () => set({ scale: 1, fitMode: 'custom' }),
  setFitMode: (fitMode) => set({ fitMode }),
  rotate: () => set((s) => ({ rotation: (s.rotation + 90) % 360 })),
  setTool: (tool) =>
    set({ tool, selection: null, openFormulaChunkId: null, openNoteId: null }),
  toggleSearch: () =>
    set((s) => ({
      searchOpen: !s.searchOpen,
      searchQuery: s.searchOpen ? '' : s.searchQuery,
      searchMatches: s.searchOpen ? [] : s.searchMatches,
      currentMatchIndex: 0,
    })),
  setSearchQuery: (searchQuery) => set({ searchQuery }),
  setSearchMatches: (searchMatches) => set({ searchMatches, currentMatchIndex: 0 }),
  setCurrentMatchIndex: (currentMatchIndex) => set({ currentMatchIndex }),
  stepMatch: (delta) =>
    set((s) => {
      const total = s.searchMatches.length
      if (total === 0) return {}
      const next = (s.currentMatchIndex + delta + total) % total
      return { currentMatchIndex: next }
    }),
  setAiPanelOpen: (aiPanelOpen) => set({ aiPanelOpen }),
  requestPrompt: (pendingPrompt) => set({ pendingPrompt, aiPanelOpen: true }),
  clearPrompt: () => set({ pendingPrompt: null }),
  setSelection: (selection) => set({ selection }),
  addAnnotation: (annotation) =>
    set((s) => {
      const page = s.annotations[annotation.page] ?? []
      const annotations = { ...s.annotations, [annotation.page]: [...page, annotation] }
      persistAnnotations(s.documentId, annotations)
      return { annotations }
    }),
  removeAnnotation: (id) =>
    set((s) => {
      const annotations: Record<number, Annotation[]> = {}
      for (const [page, list] of Object.entries(s.annotations)) {
        const filtered = list.filter((a) => a.id !== id)
        if (filtered.length > 0) annotations[Number(page)] = filtered
      }
      persistAnnotations(s.documentId, annotations)
      return { annotations }
    }),
  updateAnnotation: (id, patch) =>
    set((s) => {
      const annotations: Record<number, Annotation[]> = {}
      for (const [page, list] of Object.entries(s.annotations)) {
        annotations[Number(page)] = list.map((a) =>
          a.id === id ? ({ ...a, ...patch } as Annotation) : a,
        )
      }
      persistAnnotations(s.documentId, annotations)
      return { annotations }
    }),
  setOpenFormulaChunkId: (openFormulaChunkId) => set({ openFormulaChunkId }),
  setOpenNoteId: (openNoteId) => set({ openNoteId }),
  setFormulas: (formulas) =>
    set(() => {
      const formulasByPage: Record<number, DocumentFormulaItem[]> = {}
      for (const f of formulas) {
        if (f.page == null || !f.bbox) continue
        ;(formulasByPage[f.page] ??= []).push(f)
      }
      return { formulasByPage }
    }),
  setNotes: (notes) =>
    set(() => {
      // Только навигационные заметки (page + position) становятся маркерами.
      const notesByPage: Record<number, NoteResponse[]> = {}
      for (const n of notes) {
        if (n.page == null || !n.position || n.position.length !== 2) continue
        ;(notesByPage[n.page] ??= []).push(n)
      }
      return { notesByPage }
    }),
  setNoteDraft: (noteDraft) => set({ noteDraft }),
  requestScrollTo: (page) =>
    set((s) => ({
      scrollRequest: Math.min(Math.max(1, page), Math.max(1, s.numPages)),
      currentPage: Math.min(Math.max(1, page), Math.max(1, s.numPages)),
    })),
  clearScrollRequest: () => set({ scrollRequest: null }),
}))

export function newAnnotationId() {
  return `ann_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

/** Favourite flag per document, plain localStorage. */
export function loadFavorite(documentId: string): boolean {
  try {
    return localStorage.getItem(`ve_pdf_fav_${documentId}`) === '1'
  } catch {
    return false
  }
}

export function saveFavorite(documentId: string, value: boolean) {
  try {
    localStorage.setItem(`ve_pdf_fav_${documentId}`, value ? '1' : '0')
  } catch {
    /* ignore */
  }
}
