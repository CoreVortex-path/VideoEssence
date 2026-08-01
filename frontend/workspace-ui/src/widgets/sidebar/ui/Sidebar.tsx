import { useRef, useState, type ChangeEvent, type FormEvent } from 'react'

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
  onProcessUrl: (url: string) => void
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
  onProcessUrl,
  onRetry,
}: SidebarProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [inputMode, setInputMode] = useState<'file' | 'url'>('file')
  const [urlValue, setUrlValue] = useState('')

  const handleSelectFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    onUploadFile(file)
    event.target.value = ''
  }

  const handleUrlSubmit = (event: FormEvent) => {
    event.preventDefault()
    const trimmed = urlValue.trim()
    if (!trimmed) return
    onProcessUrl(trimmed)
    setUrlValue('')
  }

  const busy = isUploading || processingState === 'processing' || processingState === 'uploading' || processingState === 'queued'

  return (
    <aside className="flex h-full flex-col gap-3 border-r border-workspace-border bg-workspace-panel p-3">
      <input
        ref={fileInputRef}
        className="hidden"
        type="file"
        accept="audio/*,video/*"
        onChange={handleSelectFile}
      />

      <Card title="New Processing">
        <div className="space-y-2">
          <div className="flex gap-1 text-xs">
            <button
              className={[
                'flex-1 rounded px-2 py-1',
                inputMode === 'file'
                  ? 'bg-workspace-accent text-white'
                  : 'bg-workspace-muted text-slate-400 hover:text-slate-200',
              ].join(' ')}
              onClick={() => setInputMode('file')}
            >
              Upload file
            </button>
            <button
              className={[
                'flex-1 rounded px-2 py-1',
                inputMode === 'url'
                  ? 'bg-workspace-accent text-white'
                  : 'bg-workspace-muted text-slate-400 hover:text-slate-200',
              ].join(' ')}
              onClick={() => setInputMode('url')}
            >
              YouTube URL
            </button>
          </div>

          {inputMode === 'file' ? (
            <Button className="w-full" onClick={() => fileInputRef.current?.click()} disabled={busy}>
              {isUploading ? 'Uploading…' : 'Choose file…'}
            </Button>
          ) : (
            <form onSubmit={handleUrlSubmit} className="space-y-2">
              <input
                type="url"
                placeholder="https://youtu.be/…"
                value={urlValue}
                onChange={(e) => setUrlValue(e.target.value)}
                disabled={busy}
                className="w-full rounded border border-workspace-border bg-workspace-muted px-2 py-1 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-workspace-accent disabled:opacity-50"
              />
              <Button type="submit" className="w-full" disabled={busy || !urlValue.trim()}>
                {busy ? 'Processing…' : 'Process URL'}
              </Button>
            </form>
          )}
        </div>
      </Card>

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
