import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAppStore } from '../store/appStore'
import { getDocumentSnapshot, listDocuments } from '../api/client'

interface RecentProps {
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

export default function Recent({ collapsed }: RecentProps) {
  const recentIds = useAppStore((s) => s.recentDocumentIds)
  const currentDocumentId = useAppStore((s) => s.currentDocumentId)
  const openDocument = useAppStore((s) => s.openDocument)
  const markRecent = useAppStore((s) => s.markRecent)

  const { data: documents = [], isLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: listDocuments,
    staleTime: 30_000,
  })

  const recentDocuments = useMemo(() => {
    const byId = new Map(documents.map((doc) => [doc.document_id, doc]))

    return recentIds
      .map((id) => byId.get(id))
      .filter(Boolean)
      .slice(0, 5)
  }, [documents, recentIds])

  const documentIds = recentDocuments.map((doc) => doc!.document_id)

  const { data: snapshots = {} } = useQuery({
    queryKey: ['recent-document-snapshots', documentIds],
    queryFn: async () => {
      const entries = await Promise.all(
        documentIds.map(async (id) => {
          try {
            const snapshot = await getDocumentSnapshot(id)
            return [id, snapshot] as const
          } catch {
            return [id, null] as const
          }
        }),
      )

      return Object.fromEntries(entries)
    },
    enabled: documentIds.length > 0,
    staleTime: 30_000,
  })

  if (collapsed) return null

  return (
    <div>
      <div className="flex items-center px-3 pb-1 pt-2">
        <span className="text-[10px] uppercase tracking-[0.08em] text-text-faint">
          Recent
        </span>
      </div>

      {isLoading && (
        <div className="px-3 py-2 text-[11px] text-text-dim">
          Loading…
        </div>
      )}

      {!isLoading && recentDocuments.length === 0 && (
        <div className="mx-3 mb-1 rounded-md border border-border-glass/60 bg-bg-card/40 px-2.5 py-2">
          <div className="text-[11px] text-text-muted">
            No recent documents
          </div>
          <div className="mt-0.5 text-[10px] leading-4 text-text-dim">
            Open a document to see it here.
          </div>
        </div>
      )}

      {recentDocuments.map((doc) => {
        if (!doc) return null

        const snapshot = snapshots[doc.document_id]
        const title =
          snapshot?.title ||
          `${sourceInfo(doc.source_type).label} document`

        const source = sourceInfo(
          snapshot?.source_type || doc.source_type,
        )

        const active = currentDocumentId === doc.document_id

        return (
          <button
            key={doc.document_id}
            type="button"
            onClick={() => {
              markRecent(doc.document_id)
              void openDocument(doc.document_id)
            }}
            className={`group flex w-full items-center gap-2 px-3 py-1.5 text-left transition-colors ${
              active
                ? 'bg-bg-card text-text-primary'
                : 'text-text-secondary hover:bg-bg-card hover:text-text-primary'
            }`}
            title={title}
          >
            <span
              className={`flex h-5 min-w-5 items-center justify-center rounded text-[8px] font-medium ${
                active
                  ? 'bg-accent/15 text-accent'
                  : 'bg-bg-card text-text-muted'
              }`}
            >
              {source.icon}
            </span>

            <span className="min-w-0 flex-1">
              <span className="block truncate text-[12px]">
                {title}
              </span>
              <span className="block truncate text-[10px] text-text-dim">
                {source.label}
                {doc.status !== 'completed' && ` · ${doc.status}`}
              </span>
            </span>
          </button>
        )
      })}
    </div>
  )
}