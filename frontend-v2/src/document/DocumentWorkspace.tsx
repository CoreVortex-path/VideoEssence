import { useState } from 'react'
import { useAppStore } from '../store/appStore'
import { getDocumentMediaUrl } from '../api/client'
import DocumentViewer from './DocumentViewer'
import FormulasPanel from './FormulasPanel'

type DocumentTab = 'original' | 'text' | 'formulas'

const TAB_LABELS: Record<DocumentTab, string> = {
  original: 'Original',
  text: 'Text',
  formulas: 'Formulas',
}

export default function DocumentWorkspace() {
  const task = useAppStore((s) => s.currentTask)
  const documentId = useAppStore((s) => s.currentDocumentId)

  const [tab, setTab] = useState<DocumentTab>('original')

  const title = task?.title ?? 'Untitled Document'
  const isPdf = task?.source_type === 'pdf' && documentId !== null

  // FB2 и пустое состояние: оригинал показать не можем — только текст чанков.
  if (!isPdf) {
    return <DocumentViewer />
  }

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden bg-bg-panel">
      {/* Document header + view switch */}
      <div className="flex shrink-0 items-center justify-between border-b border-border px-5 py-3">
        <div className="min-w-0">
          <div className="truncate text-[14px] font-medium text-text-primary">
            {title}
          </div>

          <div className="mt-0.5 text-[10px] uppercase tracking-[0.08em] text-text-faint">
            PDF
          </div>
        </div>

        <div className="flex">
          {(['original', 'text', 'formulas'] as const).map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`px-3 py-1.5 text-[12px] transition-colors ${
                tab === id
                  ? 'border-b-2 border-accent text-text-primary'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              {TAB_LABELS[id]}
            </button>
          ))}
        </div>
      </div>

      {/* View */}
      {tab === 'original' && (
        <iframe
          src={getDocumentMediaUrl(documentId)}
          title={title}
          className="min-h-0 flex-1 border-0 bg-white"
        />
      )}
      {tab === 'text' && (
        <div className="flex min-h-0 flex-1 flex-col">
          <DocumentViewer hideHeader />
        </div>
      )}
      {tab === 'formulas' && <FormulasPanel documentId={documentId} />}
    </div>
  )
}
