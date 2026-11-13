import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useAppStore } from '../store/appStore'
import {
  deleteDocument,
  listDocuments,
  updateDocument,
} from '../api/client'

interface LibraryProps {
  collapsed: boolean
}

function sourceInfo(sourceType: string) {
  const type = sourceType.toLowerCase()

  if (type === 'youtube') {
    return { icon: '▶', label: 'YouTube' }
  }

  if (type.includes('pdf')) {
    return { icon: 'PDF', label: 'PDF' }
  }

  if (type.includes('fb2') || type.includes('epub')) {
    return { icon: '▤', label: type.includes('fb2') ? 'FB2' : 'EPUB' }
  }

  if (type.includes('video') || type.includes('media')) {
    return { icon: '▶', label: 'Video' }
  }

  return { icon: '▤', label: 'Document' }
}

interface MenuState {
  documentId: string
  top: number
  left: number
}

export default function Library({ collapsed }: LibraryProps) {
  const [expanded, setExpanded] = useState(true)
  const [menu, setMenu] = useState<MenuState | null>(null)
  const [renameId, setRenameId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const menuRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()

  const currentDocumentId = useAppStore((s) => s.currentDocumentId)
  const openDocument = useAppStore((s) => s.openDocument)
  const markRecent = useAppStore((s) => s.markRecent)
  const setDocumentId = useAppStore((s) => s.setDocumentId)
  const setCurrentTask = useAppStore((s) => s.setCurrentTask)
  const setSourceType = useAppStore((s) => s.setSourceType)
  const setMediaUrl = useAppStore((s) => s.setMediaUrl)

  const { data: documents = [], isLoading, isError } = useQuery({
    queryKey: ['documents'],
    queryFn: listDocuments,
    staleTime: 30_000,
  })

  // Закрытие меню: Esc и клик вне (клик по ⋮ обрабатывает сам toggle).
  useEffect(() => {
    if (!menu) return

    const onMouseDown = (event: MouseEvent) => {
      const target = event.target as HTMLElement
      if (target.closest('[data-menu-button]')) return
      if (menuRef.current && !menuRef.current.contains(target)) {
        setMenu(null)
      }
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenu(null)
    }

    document.addEventListener('mousedown', onMouseDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onMouseDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [menu])

  if (collapsed) return null

  const reload = () =>
    queryClient.invalidateQueries({ queryKey: ['documents'] })

  const handlePin = async (documentId: string, pinned: boolean) => {
    try {
      await updateDocument(documentId, { pinned })
      await reload()
    } catch (e) {
      console.error('[Library] pin failed:', e)
    }
  }

  const handleDelete = async (documentId: string, title: string) => {
    const ok = window.confirm(
      `Удалить «${title}»? Запись, заметки и файлы будут удалены безвозвратно.`,
    )
    if (!ok) return
    try {
      await deleteDocument(documentId)
      if (currentDocumentId === documentId) {
        // Удалён открытый документ — сброс в начальный экран (как Back в PdfHeader).
        setDocumentId(null)
        setCurrentTask(null)
        setSourceType(null)
        setMediaUrl(null)
      }
      await reload()
    } catch (e) {
      console.error('[Library] delete failed:', e)
    }
  }

  const startRename = (documentId: string, title: string) => {
    setRenameId(documentId)
    setRenameValue(title)
  }

  const submitRename = async (documentId: string, currentTitle: string) => {
    const title = renameValue.trim()
    setRenameId(null)
    if (!title || title === currentTitle) return
    try {
      await updateDocument(documentId, { title })
      await reload()
      // Заголовок открытого документа/Recent берётся из snapshot-запроса.
      await queryClient.invalidateQueries({
        queryKey: ['document-title', documentId],
      })
    } catch (e) {
      console.error('[Library] rename failed:', e)
    }
  }

  const menuDoc = menu
    ? documents.find((doc) => doc.document_id === menu.documentId)
    : null

  const docTitle = (doc: (typeof documents)[number]) =>
    doc.title || `${sourceInfo(doc.source_type).label} document`

  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="t-section-title flex w-full items-center gap-1 px-3 py-1.5 text-left transition-colors hover:text-text-primary"
      >
        <span className="w-3 text-[11px] text-text-muted">
          {expanded ? '▾' : '▸'}
        </span>
        <span className="flex-1">Library</span>

        {!isLoading && documents.length > 0 && (
          <span className="t-caption">
            {documents.length}
          </span>
        )}
      </button>

      {expanded && (
        <div className="pb-1">
          {isLoading && (
            <div className="t-caption px-6 py-2">
              Loading library…
            </div>
          )}

          {isError && (
            <div className="mx-3 rounded-md border border-amber/20 bg-amber/5 px-2.5 py-2 text-[11px] text-amber">
              Could not load library
            </div>
          )}

          {!isLoading && !isError && documents.length === 0 && (
            <div className="mx-3 rounded-md border border-border-glass/60 bg-bg-card/40 px-2.5 py-2">
              <div className="t-caption">
                No documents yet
              </div>
              <div className="t-caption mt-0.5 leading-4">
                Add a video or document with New.
              </div>
            </div>
          )}

          <div className="space-y-0.5">
            {documents.map((doc) => {
              const title = docTitle(doc)
              const source = sourceInfo(doc.source_type)
              const active = currentDocumentId === doc.document_id
              const processing = doc.status !== 'completed'
              const pinned = doc.pinned === true
              const renaming = renameId === doc.document_id
              const menuOpen = menu?.documentId === doc.document_id

              return (
                <div
                  key={doc.document_id}
                  className={`group flex w-full items-center transition-colors ${
                    active ? 'bg-bg-card' : 'hover:bg-bg-card'
                  }`}
                >
                  {renaming ? (
                    <div className="flex min-w-0 flex-1 items-center gap-2 px-3 py-2">
                      <span
                        className={`flex h-5 min-w-5 items-center justify-center rounded text-[11px] font-medium ${
                          active
                            ? 'bg-accent/15 text-accent'
                            : 'bg-bg-card text-text-muted'
                        }`}
                      >
                        {source.icon}
                      </span>
                      <input
                        ref={(el) => {
                          el?.focus()
                          el?.select()
                        }}
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            void submitRename(doc.document_id, title)
                          } else if (e.key === 'Escape') {
                            setRenameId(null)
                          }
                        }}
                        onBlur={() => setRenameId(null)}
                        className="t-card-title min-w-0 flex-1 rounded border border-accent/50 bg-bg-primary px-1.5 py-0.5 outline-none"
                      />
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => {
                        markRecent(doc.document_id)
                        void openDocument(doc.document_id)
                      }}
                      className={`flex min-w-0 flex-1 items-center gap-2 px-3 py-2 text-left transition-colors ${
                        active
                          ? 'text-text-primary'
                          : 'text-text-secondary hover:text-text-primary'
                      }`}
                      title={title}
                    >
                      <span
                        className={`flex h-5 min-w-5 items-center justify-center rounded text-[11px] font-medium ${
                          active
                            ? 'bg-accent/15 text-accent'
                            : 'bg-bg-card text-text-muted'
                        }`}
                      >
                        {source.icon}
                      </span>

                      <span className="min-w-0 flex-1">
                        <span className="t-card-title block truncate">
                          {title}
                        </span>

                        <span className="t-meta flex items-center gap-1 truncate">
                          {pinned && (
                            <>
                              <span className="text-accent">★</span>
                              <span>·</span>
                            </>
                          )}

                          <span>{source.label}</span>

                          {doc.language && (
                            <>
                              <span>·</span>
                              <span>{doc.language.toUpperCase()}</span>
                            </>
                          )}

                          {processing && (
                            <>
                              <span>·</span>
                              <span className="text-accent">
                                {doc.status}
                              </span>
                            </>
                          )}
                        </span>
                      </span>
                    </button>
                  )}

                  {/* Меню ⋮: видно при hover/focus-within, открытом меню или pinned */}
                  <button
                    type="button"
                    data-menu-button
                    title="Действия"
                    onClick={(e) => {
                      if (menuOpen) {
                        setMenu(null)
                        return
                      }
                      const rect = e.currentTarget.getBoundingClientRect()
                      setMenu({
                        documentId: doc.document_id,
                        top: rect.bottom + 4,
                        left: rect.right - 160,
                      })
                    }}
                    className={`mr-2 flex h-5 w-5 shrink-0 items-center justify-center rounded text-[13px] leading-none text-text-muted transition-opacity hover:bg-bg-card hover:text-text-primary ${
                      menuOpen || pinned
                        ? ''
                        : 'opacity-0 group-hover:opacity-100 group-focus-within:opacity-100'
                    }`}
                  >
                    ⋮
                  </button>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {menu && menuDoc && (
        <div
          ref={menuRef}
          style={{ top: menu.top, left: menu.left }}
          className="fixed z-50 w-40 rounded-md border border-border-glass bg-bg-glass py-1 shadow-lg backdrop-blur-md"
        >
          <button
            type="button"
            onClick={() => {
              setMenu(null)
              markRecent(menuDoc.document_id)
              void openDocument(menuDoc.document_id)
            }}
            className="t-secondary flex w-full items-center px-3 py-1.5 text-left transition-colors hover:bg-bg-card hover:text-text-primary"
          >
            Open
          </button>
          <button
            type="button"
            onClick={() => {
              setMenu(null)
              startRename(menuDoc.document_id, docTitle(menuDoc))
            }}
            className="t-secondary flex w-full items-center px-3 py-1.5 text-left transition-colors hover:bg-bg-card hover:text-text-primary"
          >
            Rename
          </button>
          <button
            type="button"
            onClick={() => {
              setMenu(null)
              void handlePin(menuDoc.document_id, menuDoc.pinned !== true)
            }}
            className="t-secondary flex w-full items-center px-3 py-1.5 text-left transition-colors hover:bg-bg-card hover:text-text-primary"
          >
            {menuDoc.pinned === true ? 'Unpin' : 'Pin'}
          </button>
          <button
            type="button"
            onClick={() => {
              setMenu(null)
              void handleDelete(menuDoc.document_id, docTitle(menuDoc))
            }}
            className="t-secondary flex w-full items-center px-3 py-1.5 text-left text-red-400 transition-colors hover:bg-bg-card hover:text-red-300"
          >
            Delete
          </button>
        </div>
      )}
    </div>
  )
}
