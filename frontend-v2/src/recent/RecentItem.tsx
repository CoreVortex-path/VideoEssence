import type { DocumentListItemResponse } from '../api/client'
import { useDocumentTitle } from '../library/useDocumentTitle'

interface RecentItemProps {
  doc: DocumentListItemResponse
  active: boolean
  loading: boolean
  onOpen: (documentId: string) => void
}

/** Один недавно открытый документ в списке Recent. UUID не показываем. */
export default function RecentItem({ doc, active, loading, onOpen }: RecentItemProps) {
  const isYoutube = doc.source_type === 'youtube'
  const fetchedTitle = useDocumentTitle(doc.document_id)
  const title = fetchedTitle ?? (isYoutube ? 'YouTube video' : 'Media file')

  return (
    <button
      type="button"
      title={title}
      disabled={loading}
      onClick={() => onOpen(doc.document_id)}
      className={`t-body w-full px-3 py-1.5 text-left transition-colors ${
        active
          ? 'bg-bg-card text-accent'
          : 'text-text-secondary hover:bg-bg-card hover:text-text-primary'
      } ${loading ? 'opacity-50' : ''}`}
    >
      <span className="block truncate">{title}</span>
      <span className="t-meta block">
        {isYoutube ? 'YouTube' : 'File'}
      </span>
    </button>
  )
}
