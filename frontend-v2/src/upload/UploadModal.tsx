import { useEffect, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useAppStore } from '../store/appStore'
import { processMediaFile, processMediaUrl, processDocumentFile } from '../api/client'

interface UploadModalProps {
  open: boolean
  onClose: () => void
}

type NewSourceMode = 'menu' | 'youtube'


export default function UploadModal({
  open,
  onClose,
}: UploadModalProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const documentInputRef = useRef<HTMLInputElement>(null)

  const [mode, setMode] = useState<NewSourceMode>('menu')
  const [youtubeUrl, setYoutubeUrl] = useState('')

  const setTaskId = useAppStore((s) => s.setTaskId)
  const setIsProcessing = useAppStore((s) => s.setIsProcessing)
  const setMediaUrl = useAppStore((s) => s.setMediaUrl)
  const setSourceType = useAppStore((s) => s.setSourceType)
  const selectedProfileId = useAppStore((s) => s.selectedProfileId)

  useEffect(() => {
    if (!open) return

    setMode('menu')
    setYoutubeUrl('')
  }, [open])

  useEffect(() => {
    if (!open) return

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }

    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open, onClose])

  const startTask = (
    kind: 'file_media' | 'youtube',
    url?: string,
  ) => {
    setSourceType(kind)
    setMediaUrl(url ?? null)
    setIsProcessing(true)
    onClose()
  }

  const fileMutation = useMutation({
    mutationFn: (file: File) =>
      processMediaFile(file, selectedProfileId),

    onSuccess: (res) => {
      setTaskId(res.task_id)
      startTask('file_media')
    },

    onError: (error) => {
      console.error('[Upload] file failed:', error)
    },
  })

  const urlMutation = useMutation({
    mutationFn: (url: string) =>
      processMediaUrl(url, selectedProfileId),

    onSuccess: (res, url) => {
      setTaskId(res.task_id)
      startTask('youtube', url)
    },

    onError: (error) => {
      console.error('[Upload] URL failed:', error)
    },
  })

  const documentMutation = useMutation({
  mutationFn: (file: File) =>
    processDocumentFile(file),

  onSuccess: (res) => {
    setTaskId(res.task_id)

    setSourceType('document')
    setMediaUrl(null)
    setIsProcessing(true)

    onClose()
  },

  onError: (error) => {
    console.error('[Upload] document failed:', error)
  },
})

  if (!open) return null

const busy =
  fileMutation.isPending ||
  urlMutation.isPending ||
  documentMutation.isPending

  const pickVideo = () => {
    fileInputRef.current?.click()
  }

  const pickDocument = () => {
    documentInputRef.current?.click()
  }

  const submitYoutube = () => {
    const value = youtubeUrl.trim()

    if (!value) return

    urlMutation.mutate(value)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onMouseDown={onClose}
    >
      <div
        className="glass-panel w-full max-w-[400px] rounded-xl border border-border-glass p-5 shadow-2xl"
        onMouseDown={(event) => event.stopPropagation()}
      >
        {/* Header */}
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-[15px] font-medium text-text-primary">
            {mode === 'menu' ? 'New source' : 'YouTube'}
          </h2>

          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="flex h-7 w-7 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-bg-card hover:text-text-primary"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        {mode === 'menu' ? (
          <div className="space-y-4">
            {/* Video */}
            <section>
              <div className="mb-1.5 text-[10px] uppercase tracking-[0.08em] text-text-faint">
                Video
              </div>

              <button
                type="button"
                onClick={pickVideo}
                disabled={busy}
                className="group flex w-full items-center gap-3 rounded-lg border border-border-glass bg-bg-card/50 px-3 py-3 text-left transition-colors hover:border-accent/40 hover:bg-bg-card disabled:opacity-40"
              >
                <span className="flex h-9 w-9 items-center justify-center rounded-md bg-accent/10 text-accent">
                  ▶
                </span>

                <span className="min-w-0">
                  <span className="block text-[13px] text-text-primary">
                    Upload video
                  </span>

                  <span className="block text-[11px] text-text-dim">
                    MP4, MKV, MOV, WebM and other supported formats
                  </span>
                </span>
              </button>
            </section>

            {/* Document */}
            <section>
              <div className="mb-1.5 text-[10px] uppercase tracking-[0.08em] text-text-faint">
                Document
              </div>

              <button
                type="button"
                onClick={pickDocument}
                disabled={busy}
                className="group flex w-full items-center gap-3 rounded-lg border border-border-glass bg-bg-card/50 px-3 py-3 text-left transition-colors hover:border-accent/40 hover:bg-bg-card disabled:opacity-40"
              >
                <span className="flex h-9 w-9 items-center justify-center rounded-md bg-accent/10 text-accent">
                  ▤
                </span>

                <span className="min-w-0">
                  <span className="block text-[13px] text-text-primary">
                    Upload document
                  </span>

                  <span className="block text-[11px] text-text-dim">
                    PDF, FB2
                  </span>
                </span>
              </button>
            </section>

            {/* YouTube */}
            <section>
              <div className="mb-1.5 text-[10px] uppercase tracking-[0.08em] text-text-faint">
                YouTube
              </div>

              <button
                type="button"
                onClick={() => setMode('youtube')}
                disabled={busy}
                className="group flex w-full items-center gap-3 rounded-lg border border-border-glass bg-bg-card/50 px-3 py-3 text-left transition-colors hover:border-accent/40 hover:bg-bg-card disabled:opacity-40"
              >
                <span className="flex h-9 w-9 items-center justify-center rounded-md bg-accent/10 text-accent">
                  ◉
                </span>

                <span className="min-w-0">
                  <span className="block text-[13px] text-text-primary">
                    YouTube URL
                  </span>

                  <span className="block text-[11px] text-text-dim">
                    Paste a video link
                  </span>
                </span>
              </button>
            </section>
          </div>
        ) : (
          <div>
            <label className="mb-2 block text-[11px] text-text-secondary">
              YouTube URL
            </label>

            <input
              autoFocus
              value={youtubeUrl}
              onChange={(event) =>
                setYoutubeUrl(event.target.value)
              }
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault()
                  submitYoutube()
                }
              }}
              placeholder="https://youtube.com/watch?v=..."
              disabled={busy}
              className="w-full rounded-md border border-border-glass bg-bg-card px-3 py-2 text-[13px] text-text-primary outline-none placeholder:text-text-dim focus:border-accent/50"
            />

            {urlMutation.isError && (
              <div className="mt-2 rounded-md border border-amber/30 bg-amber/5 px-2.5 py-2 text-[11px] text-amber">
                Не удалось запустить обработку
              </div>
            )}

            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setMode('menu')}
                disabled={busy}
                className="rounded-md px-3 py-2 text-[12px] text-text-secondary hover:bg-bg-card hover:text-text-primary"
              >
                Back
              </button>

              <button
                type="button"
                onClick={submitYoutube}
                disabled={busy || !youtubeUrl.trim()}
                className="rounded-md bg-accent px-3 py-2 text-[12px] text-white transition-colors hover:bg-accent-hover disabled:opacity-40"
              >
                {urlMutation.isPending ? 'Adding…' : 'Add'}
              </button>
            </div>
          </div>
        )}

        {fileMutation.isError && (
          <div className="mt-3 rounded-md border border-amber/30 bg-amber/5 px-2.5 py-2 text-[11px] text-amber">
            Не удалось загрузить файл
          </div>
        )}

        {/* Video input */}
        <input
          ref={fileInputRef}
          type="file"
          accept="video/*"
          className="hidden"
          onChange={(event) => {
  const file = event.target.files?.[0]

  if (!file) {
    event.target.value = ''
    return
  }

  fileMutation.mutate(file)

  event.target.value = ''
}}
        />

        {/* Document input — PDF/FB2 идут через тот же /videos/process-file,
            backend сам выбирает document pipeline по расширению. */}
        <input
          ref={documentInputRef}
          type="file"
          accept=".pdf,.fb2,application/pdf"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0]

            if (!file) {
              event.target.value = ''
              return
            }

            documentMutation.mutate(file)

            event.target.value = ''
          }}
        />
      </div>
    </div>
  )
}