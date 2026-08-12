import { useCallback, useEffect, useState } from 'react'
import { listDocuments, type DocumentListItemResponse } from '../api/client'
import { useAppStore } from '../store/appStore'
import RecentItem from './RecentItem'

interface RecentProps {
  collapsed: boolean
}

/** Последние открытые документы (макс. 8). Это быстрый доступ, не Storage. */
export default function Recent({ collapsed }: RecentProps) {
  const [expanded, setExpanded] = useState(false)
  const [docs, setDocs] = useState<DocumentListItemResponse[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loadingId, setLoadingId] = useState<string | null>(null)

  const openDocument = useAppStore((s) => s.openDocument)
  const markRecent = useAppStore((s) => s.markRecent)
  const currentDocumentId = useAppStore((s) => s.currentDocumentId)
  const recentDocumentIds = useAppStore((s) => s.recentDocumentIds)

  const refresh = useCallback(() => {
    setError(null)
    listDocuments()
      .then(setDocs)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
  }, [])

  useEffect(() => {
    if (expanded && !collapsed) refresh()
  }, [expanded, collapsed, refresh])

  const handleOpen = useCallback(
    (documentId: string) => {
      if (loadingId) return
      setLoadingId(documentId)
      openDocument(documentId)
        .then(() => markRecent(documentId))
        .catch((e: unknown) =>
          setError(e instanceof Error ? e.message : String(e)),
        )
        .finally(() => setLoadingId(null))
    },
    [openDocument, markRecent, loadingId],
  )

  // Recent — только последние открытые, в порядке открытия
  const recentDocs = (docs ?? [])
    .filter((d) => recentDocumentIds.includes(d.document_id))
    .sort(
      (a, b) =>
        recentDocumentIds.indexOf(a.document_id) -
        recentDocumentIds.indexOf(b.document_id),
    )

  if (collapsed) {
    return (
      <button
        type="button"
        title="Recent"
        className="w-full truncate px-3 py-1.5 text-left text-[13px] text-text-secondary transition-colors hover:bg-bg-card hover:text-text-primary"
      >
        R
      </button>
    )
  }

  return (
    <div>
      <button
        type="button"
        title="Recent"
        onClick={() => setExpanded((v) => !v)}
        className={`w-full truncate px-3 py-1.5 text-left text-[13px] transition-colors ${
          expanded
            ? 'bg-bg-card text-accent'
            : 'text-text-secondary hover:bg-bg-card hover:text-text-primary'
        }`}
      >
        {expanded ? '▾ Recent' : '▸ Recent'}
      </button>
      {expanded && (
        <div className="pl-2">
          {error && (
            <div className="px-3 py-1 text-[11px] text-red-400" title={error}>
              Ошибка загрузки
            </div>
          )}
          {!error && docs === null && (
            <div className="px-3 py-1 text-[11px] text-text-faint">Загрузка…</div>
          )}
          {!error && docs !== null && recentDocs.length === 0 && (
            <div className="px-3 py-1 text-[11px] text-text-faint">Нет недавних</div>
          )}
          {recentDocs.map((doc) => (
            <RecentItem
              key={doc.document_id}
              doc={doc}
              active={doc.document_id === currentDocumentId}
              loading={loadingId === doc.document_id}
              onOpen={handleOpen}
            />
          ))}
        </div>
      )}
    </div>
  )
}
