import type { DocumentListItemResponse } from '../api/client'
import { useDocumentTitle } from './useDocumentTitle'

interface LibraryItemProps {
  doc: DocumentListItemResponse
  active: boolean
  loading: boolean
  onOpen: (documentId: string) => void
}

/** Один сохранённый документ в Library. UUID пользователю не показываем. */
export default function LibraryItem({ doc, active, loading, onOpen }: LibraryItemProps) {
  const isYoutube = doc.source_type === 'youtube'
  const fetchedTitle = useDocumentTitle(doc.document_id)
  const title = fetchedTitle ?? (isYoutube ? 'YouTube video' : 'Media file')

  return (
    <button
      type="button"
      title={title}
      disabled={loading}
      onClick={() => onOpen(doc.document_id)}
      className={`w-full px-3 py-1.5 text-left text-[13px] transition-colors ${
        active
          ? 'bg-bg-card text-accent'
          : 'text-text-secondary hover:bg-bg-card hover:text-text-primary'
      } ${loading ? 'opacity-50' : ''}`}
    >
      <span className="block truncate">{title}</span>
      <span className="block text-[11px] text-text-faint">
        {isYoutube ? 'YouTube' : 'File'}
      </span>
    </button>
  )
}
