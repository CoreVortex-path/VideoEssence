import { useCallback, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getDocumentFormulas, getDocumentMediaUrl, getNotes } from '../api/client'
import { useAppStore } from '../store/appStore'
import { usePdfStore } from './pdfStore'
import { usePdfDocument } from './usePdfDocument'
import PdfHeader from './PdfHeader'
import PdfBottomBar from './PdfBottomBar'
import PdfViewer from './PdfViewer'
import ThumbnailsPanel from './ThumbnailsPanel'
import ToolsPalette from './ToolsPalette'
import SearchBar from './SearchBar'
import './pdf.css'

/**
 * Smart PDF Workspace: header + thumbnails/outline + integrated viewer
 * (canvas, text layer, Konva annotations, formula regions, notes, search)
 * + bottom bar.
 */
export default function PdfWorkspace({ documentId }: { documentId: string }) {
  const reset = usePdfStore((s) => s.reset)
  const setNumPages = usePdfStore((s) => s.setNumPages)
  const setFormulas = usePdfStore((s) => s.setFormulas)
  const setNotes = usePdfStore((s) => s.setNotes)
  const searchOpen = usePdfStore((s) => s.searchOpen)

  const pendingNoteAnchor = useAppStore((s) => s.pendingNoteAnchor)
  const setPendingNoteAnchor = useAppStore((s) => s.setPendingNoteAnchor)

  const rootRef = useRef<HTMLDivElement>(null)
  const { doc, error } = usePdfDocument(getDocumentMediaUrl(documentId))

  // Fresh viewer state per document (annotations hydrate from localStorage).
  useEffect(() => {
    reset(documentId)
  }, [documentId, reset])

  useEffect(() => {
    if (doc) setNumPages(doc.numPages)
  }, [doc, setNumPages])

  // Detected formulas → per-page regions on the overlay.
  const { data: formulas } = useQuery({
    queryKey: ['pdf-formulas', documentId],
    queryFn: () => getDocumentFormulas(documentId),
  })
  useEffect(() => {
    setFormulas(formulas ?? [])
  }, [formulas, setFormulas])

  // Backend notes → per-page markers (anchor lives on the note itself).
  const { data: notes } = useQuery({
    queryKey: ['notes', documentId],
    queryFn: () => getNotes(documentId),
  })
  useEffect(() => {
    setNotes(notes ?? [])
  }, [notes, setNotes])

  // Navigation contract from the global notes list: open → page → scroll →
  // focus the note popover.
  useEffect(() => {
    if (!doc || !pendingNoteAnchor || pendingNoteAnchor.documentId !== documentId) return
    if (pendingNoteAnchor.page != null) {
      usePdfStore.getState().requestScrollTo(pendingNoteAnchor.page)
      if (pendingNoteAnchor.position) {
        usePdfStore.getState().setOpenNoteId(pendingNoteAnchor.noteId)
      }
    }
    setPendingNoteAnchor(null)
  }, [doc, pendingNoteAnchor, documentId, setPendingNoteAnchor])

  const toggleFullscreen = useCallback(() => {
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => undefined)
    } else {
      rootRef.current?.requestFullscreen().catch(() => undefined)
    }
  }, [])

  return (
    <div
      ref={rootRef}
      className="flex h-full min-h-0 w-full flex-col overflow-hidden bg-bg-primary"
    >
      <PdfHeader documentId={documentId} onToggleFullscreen={toggleFullscreen} />

      <div className="flex min-h-0 flex-1">
        {doc && <ThumbnailsPanel doc={doc} />}

        <div className="relative flex min-w-0 flex-1 flex-col">
          {searchOpen && doc && (
            <div className="absolute right-4 top-3 z-20">
              <SearchBar doc={doc} />
            </div>
          )}

          {error && (
            <div className="flex flex-1 items-center justify-center px-6 text-center text-[13px] text-amber">
              Не удалось загрузить PDF: {error}
            </div>
          )}
          {!doc && !error && (
            <div className="flex flex-1 items-center justify-center text-[13px] text-text-faint">
              Loading PDF…
            </div>
          )}
          {doc && <PdfViewer doc={doc} documentId={documentId} />}

          {doc && <ToolsPalette />}
        </div>
      </div>

      <PdfBottomBar onToggleFullscreen={toggleFullscreen} />
    </div>
  )
}
