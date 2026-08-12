import { useState } from 'react'
import { useAppStore } from '../store/appStore'
import { importTranslation } from '../api/client'

export default function TranslationView() {
  const task = useAppStore((s) => s.currentTask)
  const taskId = useAppStore((s) => s.currentTaskId)
  const segments = useAppStore((s) => s.transcriptSegments)
  const trans = useAppStore((s) => s.translationSegments)
  const setTranslationSegments = useAppStore((s) => s.setTranslationSegments)
  const lang = useAppStore((s) => s.targetLanguage)

  const [importOpen, setImportOpen] = useState(false)
  const [importText, setImportText] = useState('')
  const [importing, setImporting] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)

  if (!task) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center text-[13px] text-text-faint">
        Process a video first
      </div>
    )
  }
  if (task.status !== 'completed') {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center text-[13px] text-text-faint">
        Translation will appear after processing…
      </div>
    )
  }

  const original = segments.map((s) => s.text).join(' ')
  const translatedCount = trans.filter((s) => s.enrichment?.translation).length
  const failedCount = trans.length - translatedCount
  const translated = trans.length
    ? trans
        .map((s) => s.enrichment?.translation ?? '')
        .filter(Boolean)
        .join(' ')
    : ''

  const handleImport = async () => {
    if (!taskId) return
    if (!importText.trim()) {
      setImportError('Вставьте текст перевода')
      return
    }
    setImporting(true)
    setImportError(null)
    try {
      const res = await importTranslation(taskId, lang, importText.trim())
      setTranslationSegments(res.transcript_segments ?? [])
      setImportOpen(false)
      setImportText('')
    } catch (e) {
      setImportError(String(e))
    } finally {
      setImporting(false)
    }
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="flex items-center gap-2 px-4 pt-2">
        <button
          type="button"
          onClick={() => {
            setImportOpen(true)
            setImportError(null)
          }}
          className="rounded border border-border-glass bg-bg-card px-3 py-1 text-[11px] text-text-secondary transition-colors hover:text-text-primary"
        >
          Import Translation
        </button>
      </div>

      {failedCount > 0 && (
        <div className="mx-4 mt-2 rounded border border-amber/40 px-3 py-1.5 text-[12px] text-amber">
          Переведено частично: {translatedCount} из {trans.length} сегментов. Запустите перевод
          ещё раз, чтобы догрузить оставшиеся.
        </div>
      )}

      <div className="grid h-full grid-cols-2 gap-4 p-4">
        <div className="flex flex-col">
          <div className="sticky top-0 mb-2 bg-bg-secondary pb-1 text-[11px] uppercase tracking-wide text-text-faint">
            Original
          </div>
          <div className="text-[13px] leading-relaxed text-text-secondary">
            {original}
          </div>
        </div>
        <div className="flex flex-col">
          <div className="sticky top-0 mb-2 bg-bg-secondary pb-1 text-[11px] uppercase tracking-wide text-text-faint">
            {lang.toUpperCase()}
          </div>
          <div className="text-[13px] leading-relaxed text-text-muted">
            {translated || '—'}
          </div>
        </div>
      </div>

      {importOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="flex w-[480px] max-w-[90vw] flex-col gap-2 rounded border border-border-glass bg-bg-secondary p-4">
            <div className="text-[13px] text-text-primary">Import Translation</div>
            <div className="text-[11px] text-text-faint">
              Вставьте готовый перевод целиком. Система сама разобьёт его на {segments.length} сегментов.
            </div>
            <textarea
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              rows={10}
              placeholder={'Вставьте полный текст перевода здесь...'}
              className="w-full resize-y rounded border border-border-glass bg-bg-card p-2 text-[12px] text-text-secondary outline-none"
            />
            {importError && (
              <div className="rounded border border-amber/40 px-3 py-1.5 text-[12px] text-amber">
                {importError}
              </div>
            )}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setImportOpen(false)}
                className="rounded border border-border-glass px-3 py-1 text-[11px] text-text-secondary hover:text-text-primary"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleImport}
                disabled={importing || !importText.trim()}
                className="rounded bg-accent px-3 py-1 text-[11px] text-white transition-colors hover:bg-accent-hover disabled:opacity-40"
              >
                {importing ? 'Importing…' : 'Import'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}