import { useCallback, useEffect, useState } from 'react'
import {
  getDocumentFormulas,
  getFormulaImageUrl,
  recognizeFormulas,
} from '../api/client'
import type { DocumentFormulaItem } from '../api/client'

interface FormulasPanelProps {
  documentId: string
}

export default function FormulasPanel({ documentId }: FormulasPanelProps) {
  const [formulas, setFormulas] = useState<DocumentFormulaItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pendingIds, setPendingIds] = useState<Set<string>>(new Set())

  useEffect(() => {
    let cancelled = false
    getDocumentFormulas(documentId)
      .then((items) => {
        if (!cancelled) setFormulas(items)
      })
      .catch((e) => {
        if (!cancelled) setError(String(e))
      })
    return () => {
      cancelled = true
    }
  }, [documentId])

  const recognize = useCallback(
    async (chunkId: string) => {
      setPendingIds((prev) => new Set(prev).add(chunkId))
      setError(null)
      try {
        const res = await recognizeFormulas(documentId, [chunkId])
        setFormulas(res.formulas)
      } catch (e) {
        setError(String(e))
      } finally {
        setPendingIds((prev) => {
          const next = new Set(prev)
          next.delete(chunkId)
          return next
        })
      }
    },
    [documentId],
  )

  if (error && formulas === null) {
    return (
      <div className="flex min-h-[200px] items-center justify-center px-6 text-center text-[12px] text-amber">
        {error}
      </div>
    )
  }

  if (formulas === null) {
    return (
      <div className="flex min-h-[200px] items-center justify-center text-[13px] text-text-faint">
        Loading formulas…
      </div>
    )
  }

  if (formulas.length === 0) {
    return (
      <div className="flex min-h-[200px] items-center justify-center text-[13px] text-text-faint">
        No formulas detected in this document.
      </div>
    )
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      {error && (
        <div className="mx-4 mt-3 rounded-md border border-amber/30 bg-amber/5 px-2.5 py-2 text-[11px] text-amber">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2">
        {formulas.map((formula) => {
          const pending = pendingIds.has(formula.chunk_id)

          return (
            <div
              key={formula.chunk_id}
              className="rounded-lg border border-border-glass bg-bg-card/50 p-3"
            >
              <div className="mb-2 flex items-center justify-between text-[10px] uppercase tracking-[0.08em] text-text-faint">
                <span>
                  {formula.page != null ? `Page ${formula.page}` : 'Formula'}
                </span>
                <span>{formula.kind.replace('formula_', '')}</span>
              </div>

              {formula.has_image && (
                <img
                  src={getFormulaImageUrl(documentId, formula.chunk_id)}
                  alt={`Formula on page ${formula.page ?? '?'}`}
                  className="mb-2 max-h-40 rounded bg-white object-contain"
                  loading="lazy"
                />
              )}

              {formula.latex ? (
                <code className="block whitespace-pre-wrap break-words rounded bg-bg-panel px-2 py-1.5 text-[12px] text-text-primary">
                  {formula.latex}
                </code>
              ) : formula.has_image ? (
                <button
                  type="button"
                  onClick={() => recognize(formula.chunk_id)}
                  disabled={pending}
                  className="rounded bg-accent px-3 py-1 text-[11px] text-white transition-colors hover:bg-accent-hover disabled:opacity-40"
                >
                  {pending
                    ? 'Recognizing…'
                    : formula.status === 'failed'
                      ? 'Retry recognition'
                      : 'Recognize LaTeX'}
                </button>
              ) : (
                <span className="text-[11px] text-text-faint">
                  No image available
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
