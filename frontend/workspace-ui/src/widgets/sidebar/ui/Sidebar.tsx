import { useRef, type ChangeEvent } from 'react'

import type { DocumentListItem } from '@/entities/document/model/types'
import { Button } from '@/shared/ui/Button'
import { Card } from '@/shared/ui/Card'

interface SidebarProps {
  documents: DocumentListItem[]
  activeDocumentId: string | null
  processingState: 'idle' | 'uploading' | 'queued' | 'processing' | 'completed' | 'failed'
  processingMessage: string
  processingError: string | null
  isUploading: boolean
  onSelectDocument: (documentId: string) => void
  onOpenTab: (tab: 'search' | 'notes' | 'translation') => void
  onUploadFile: (file: File) => void
  onRetry: () => void
}

export function Sidebar({
  documents,
  activeDocumentId,
  processingState,
  processingMessage,
  processingError,
  isUploading,
  onSelectDocument,
  onOpenTab,
  onUploadFile,
  onRetry,
}: SidebarProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleSelectFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }
    onUploadFile(file)
    event.target.value = ''
  }

  return (
    <aside className="flex h-full flex-col gap-3 border-r border-workspace-border bg-workspace-panel p-3">
      <input
        ref={fileInputRef}
        className="hidden"
        type="file"
        accept="audio/*,video/*"
        onChange={handleSelectFile}
      />
      <Button className="w-full" onClick={() => fileInputRef.current?.click()} disabled={isUploading}>
        {isUploading ? 'Uploading…' : 'New Processing'}
      </Button>

      <Card title="Processing">
        <div className="space-y-2 text-sm">
          <p className="text-slate-300">{processingMessage}</p>
          {processingError ? <p className="text-red-400">{processingError}</p> : null}
          {processingState === 'failed' ? (
            <Button className="w-full" variant="ghost" onClick={onRetry}>
              Retry
            </Button>
          ) : null}
        </div>
      </Card>

      <Card title="Documents">
        <ul className="space-y-2">
          {documents.map((document) => {
            const selected = document.id === activeDocumentId
            return (
              <li key={document.id}>
                <button
                  className={[
                    'w-full rounded-lg border p-2 text-left text-xs',
                    selected
                      ? 'border-workspace-accent bg-workspace-muted'
                      : 'border-workspace-border bg-workspace-panel hover:bg-workspace-muted',
                  ].join(' ')}
                  onClick={() => onSelectDocument(document.id)}
                >
                  <p className="font-semibold text-slate-100">{document.title}</p>
                  <p className="mt-1 text-slate-400">{document.language}</p>
                  <p className="text-slate-500">{document.status}</p>
                  <p className="text-slate-500">{document.progress}</p>
                </button>
              </li>
            )
          })}
        </ul>
      </Card>

      <Card title="Quick tools">
        <div className="grid gap-2">
          <Button variant="ghost" onClick={() => onOpenTab('search')}>
            Search
          </Button>
          <Button variant="ghost" onClick={() => onOpenTab('notes')}>
            Notes
          </Button>
          <Button variant="ghost" onClick={() => onOpenTab('translation')}>
            Translation
          </Button>
        </div>
      </Card>
    </aside>
  )
}
