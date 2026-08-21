import { useEffect, useState } from 'react'
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'
import type { PDFDocumentProxy } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

// Worker is shared app-wide; setting it repeatedly is idempotent.
GlobalWorkerOptions.workerSrc = workerUrl

/** Loads a PDFDocumentProxy from a URL and destroys it on unmount/url change. */
export function usePdfDocument(url: string | null) {
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!url) {
      setDoc(null)
      setError(null)
      return
    }
    let cancelled = false
    setDoc(null)
    setError(null)

    const task = getDocument({ url })
    task.promise.then(
      (loaded) => {
        if (!cancelled) setDoc(loaded)
      },
      (e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      },
    )

    return () => {
      cancelled = true
      task.destroy().catch(() => undefined)
    }
  }, [url])

  return { doc, error }
}
