import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  createNote,
  getFormulaImageUrl,
  recognizeFormulas,
} from '../api/client'
import type { DocumentFormulaItem } from '../api/client'
import { useAppStore } from '../store/appStore'
import { usePdfStore } from './pdfStore'
import { AiIcon, CloseIcon, CopyIcon } from './icons'

interface FormulaPopoverProps {
  documentId: string
  formula: DocumentFormulaItem
}

/** Popover for a detected formula region: LaTeX / recognize / copy / AI / save. */
export default function FormulaPopover({ documentId, formula }: FormulaPopoverProps) {
  const setOpenFormulaChunkId = usePdfStore((s) => s.setOpenFormulaChunkId)
  const requestPrompt = usePdfStore((s) => s.requestPrompt)
  const setChatMode = useAppStore((s) => s.setChatMode)
  const queryClient = useQueryClient()

  const recognizeMutation = useMutation({
    mutationFn: () => recognizeFormulas(documentId, [formula.chunk_id]),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['pdf-formulas', documentId] }),
  })

  const saveMutation = useMutation({
    mutationFn: () =>
      createNote(documentId, {
        text: formula.latex ?? `Formula (page ${formula.page ?? '?'})`,
        selected_text: formula.latex,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notes', documentId] }),
  })

  const askAi = (prefix: string) => {
    setChatMode('document')
    requestPrompt(`${prefix}\n\n${formula.latex ?? `Formula on page ${formula.page ?? '?'}`}`)
    setOpenFormulaChunkId(null)
  }

  const btn =
    'rounded border border-border-glass px-2 py-0.5 text-[11px] text-text-secondary transition-colors hover:border-accent hover:text-text-primary disabled:opacity-40'

  return (
    <div
      onMouseDown={(e) => e.stopPropagation()}
      className="flex w-[260px] flex-col gap-2 rounded-md border border-border-glass bg-bg-glass p-2.5 shadow-lg backdrop-blur-md"
    >
      <div className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-[0.08em] text-text-faint">
          Formula{formula.page != null ? ` · page ${formula.page}` : ''}
        </span>
        <button
          type="button"
          onClick={() => setOpenFormulaChunkId(null)}
          className="rounded p-0.5 text-text-muted hover:bg-bg-card hover:text-text-primary"
        >
          <CloseIcon className="h-3 w-3" />
        </button>
      </div>

      {formula.latex ? (
        <code className="block max-h-32 overflow-y-auto whitespace-pre-wrap break-words rounded bg-bg-secondary px-2 py-1.5 text-[12px] text-text-primary">
          {formula.latex}
        </code>
      ) : formula.has_image ? (
        <>
          <img
            src={getFormulaImageUrl(documentId, formula.chunk_id)}
            alt="Formula"
            className="max-h-32 rounded bg-white object-contain"
          />
          <button
            type="button"
            onClick={() => recognizeMutation.mutate()}
            disabled={recognizeMutation.isPending}
            className="rounded bg-accent px-2.5 py-1 text-[11px] text-white transition-colors hover:bg-accent-hover disabled:opacity-40"
          >
            {recognizeMutation.isPending
              ? 'Recognizing…'
              : formula.status === 'failed'
                ? 'Retry recognition'
                : 'Recognize LaTeX'}
          </button>
          {recognizeMutation.isError && (
            <span className="text-[11px] text-amber">Не удалось распознать</span>
          )}
        </>
      ) : (
        <span className="text-[11px] text-text-faint">No image available</span>
      )}

      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          onClick={() => {
            if (formula.latex) navigator.clipboard.writeText(formula.latex).catch(() => undefined)
          }}
          disabled={!formula.latex}
          className={btn}
          title="Copy LaTeX"
        >
          <span className="inline-flex items-center gap-1">
            <CopyIcon className="h-3 w-3" /> LaTeX
          </span>
        </button>
        <button type="button" onClick={() => askAi('Объясни формулу из документа:')} className={`${btn} text-purple`}>
          <span className="inline-flex items-center gap-1">
            <AiIcon className="h-3 w-3" /> Explain
          </span>
        </button>
        <button type="button" onClick={() => askAi('Вопрос по формуле из документа:')} className={`${btn} text-purple`}>
          Ask AI
        </button>
        <button
          type="button"
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending || saveMutation.isSuccess}
          className={btn}
        >
          {saveMutation.isSuccess ? 'Saved' : saveMutation.isPending ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  )
}
