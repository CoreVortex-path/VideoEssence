import { useRef } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useAppStore } from '../store/appStore'
import { processMediaFile, processMediaUrl } from '../api/client'

interface UploadModalProps {
  open: boolean
  onClose: () => void
}

export default function UploadModal({ open, onClose }: UploadModalProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const setTaskId = useAppStore((s) => s.setTaskId)
  const setIsProcessing = useAppStore((s) => s.setIsProcessing)
  const setMediaUrl = useAppStore((s) => s.setMediaUrl)
  const setSourceType = useAppStore((s) => s.setSourceType)
  const setWaveformPeaks = useAppStore((s) => s.setWaveformPeaks)
  const selectedProfileId = useAppStore((s) => s.selectedProfileId)

  const fileMutation = useMutation({
    mutationFn: (file: File) => processMediaFile(file, selectedProfileId),
    onSuccess: (res) => {
      setTaskId(res.task_id)
      setIsProcessing(true)
      onClose()
    },
    onError: (e) => console.error('[Upload] file failed:', e),
  })

  const urlMutation = useMutation({
    mutationFn: (url: string) => processMediaUrl(url, selectedProfileId),
    onSuccess: (res, url) => {
      setTaskId(res.task_id)
      setSourceType('youtube')
      setMediaUrl(url)
      setIsProcessing(true)
      onClose()
    },
    onError: (e) => console.error('[Upload] url failed:', e),
  })

  if (!open) return null

  const pickFile = () => fileInputRef.current?.click()

  const pasteUrl = () => {
    const url = window.prompt('YouTube URL:')
    if (url?.trim()) urlMutation.mutate(url.trim())
  }

  const busy = fileMutation.isPending || urlMutation.isPending

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center backdrop-blur-sm"
      style={{ background: 'rgba(12,10,15,0.5)' }}
      onClick={onClose}
    >
      <div
        className="glass-panel w-full max-w-[360px] rounded-lg border p-4 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-3 text-[14px] font-medium text-text-primary">
          Новый источник
        </h2>
        <div className="flex flex-col gap-2">
          <button
            type="button"
            onClick={pickFile}
            disabled={busy}
            className="rounded-md bg-accent px-3 py-2 text-[13px] text-white transition-colors hover:bg-accent-hover disabled:opacity-40"
          >
            {fileMutation.isPending ? 'Uploading…' : 'Upload Video'}
          </button>
          <button
            type="button"
            onClick={pasteUrl}
            disabled={busy}
            className="rounded-md border border-border-primary px-3 py-2 text-[13px] text-text-secondary transition-colors hover:bg-bg-card hover:text-text-primary disabled:opacity-40"
          >
            {urlMutation.isPending ? 'Sending…' : 'Paste URL'}
          </button>
        </div>
        {(fileMutation.isError || urlMutation.isError) && (
          <div className="mt-2 animate-pulse rounded border border-amber/40 p-2 text-[12px] text-amber">
            Не удалось запустить обработку
          </div>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept="video/*"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) {
              const blobUrl = URL.createObjectURL(file)
              setMediaUrl(blobUrl)
              setSourceType('file_media')
              setWaveformPeaks(null)  // сброс старых peaks
              fileMutation.mutate(file)
            }
            e.target.value = ''
          }}
        />
      </div>
    </div>
  )
}