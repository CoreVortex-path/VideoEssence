import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { translateText } from '../api/client'
import { useAppStore } from '../store/appStore'
import { newAnnotationId, usePdfStore } from './pdfStore'

/**
 * Contextual toolbar shown next to a non-collapsed text selection:
 * Highlight | Note | Explain | Translate | Ask AI | Copy.
 */
export default function SelectionToolbar() {
  const selection = usePdfStore((s) => s.selection)
  const addAnnotation = usePdfStore((s) => s.addAnnotation)
  const setSelection = usePdfStore((s) => s.setSelection)
  const setNoteDraft = usePdfStore((s) => s.setNoteDraft)
  const requestPrompt = usePdfStore((s) => s.requestPrompt)
  const setChatMode = useAppStore((s) => s.setChatMode)

  const [translation, setTranslation] = useState<string | null>(null)

  const translateMutation = useMutation({
    mutationFn: (text: string) => translateText(text),
    onSuccess: (res) => setTranslation(res.translation),
  })

  if (!selection) return null

  const clearNativeSelection = () => window.getSelection()?.removeAllRanges()
  const close = () => {
    setSelection(null)
    setTranslation(null)
  }

  const highlight = () => {
    addAnnotation({
      id: newAnnotationId(),
      type: 'highlight',
      page: selection.page,
      rects: selection.rects,
    })
    clearNativeSelection()
    close()
  }

  const makeNote = () => {
    setNoteDraft({
      page: selection.page,
      x: selection.noteAnchor[0],
      y: selection.noteAnchor[1],
      selectedText: selection.text,
    })
    clearNativeSelection()
    close()
  }

  const askAi = (prefix: string) => {
    setChatMode('document')
    requestPrompt(`${prefix}\n\n«${selection.text}»`)
    close()
  }

  const copy = () => {
    navigator.clipboard.writeText(selection.text).catch(() => undefined)
    close()
  }

  const btn =
    'px-2 py-1 text-[11px] text-text-secondary transition-colors hover:bg-bg-card hover:text-text-primary'

  return (
    <div
      // onMouseDown preventDefault: не даём клику сбросить выделение раньше обработчика
      onMouseDown={(e) => e.preventDefault()}
      className="flex flex-col rounded-md border border-border-glass bg-bg-glass shadow-lg backdrop-blur-md"
    >
      <div className="flex items-center divide-x divide-border-glass">
        <button type="button" onClick={highlight} className={btn}>
          Highlight
        </button>
        <button type="button" onClick={makeNote} className={btn}>
          Note
        </button>
        <button
          type="button"
          onClick={() => askAi('Объясни фрагмент из документа:')}
          className={`${btn} text-purple`}
        >
          Explain
        </button>
        <button
          type="button"
          onClick={() => {
            setTranslation(null)
            translateMutation.mutate(selection.text)
          }}
          className={btn}
        >
          Translate
        </button>
        <button
          type="button"
          onClick={() => askAi('Вопрос по фрагменту из документа:')}
          className={`${btn} text-purple`}
        >
          Ask AI
        </button>
        <button type="button" onClick={copy} className={btn}>
          Copy
        </button>
      </div>
      {(translateMutation.isPending || translation || translateMutation.isError) && (
        <div className="max-w-[280px] border-t border-border-glass px-2 py-1.5 text-[11px] text-text-secondary">
          {translateMutation.isPending && 'Translating…'}
          {translateMutation.isError && <span className="text-amber">Ошибка перевода</span>}
          {translation && <span className="whitespace-pre-wrap">{translation}</span>}
        </div>
      )}
    </div>
  )
}
