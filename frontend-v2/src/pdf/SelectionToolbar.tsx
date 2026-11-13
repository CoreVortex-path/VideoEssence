import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { translateText } from '../api/client'
import FloatingSelectionToolbar from '../selection/FloatingSelectionToolbar'
import { useAppStore } from '../store/appStore'
import { newAnnotationId, usePdfStore } from './pdfStore'

/**
 * Contextual toolbar shown next to a non-collapsed text selection:
 * Highlight | Note | Explain | Translate | Ask AI | Copy.
 * Визуал — общий FloatingSelectionToolbar; здесь только PDF-логика действий.
 */
export default function SelectionToolbar() {
  const selection = usePdfStore((s) => s.selection)
  const addAnnotation = usePdfStore((s) => s.addAnnotation)
  const setSelection = usePdfStore((s) => s.setSelection)
  const setNoteDraft = usePdfStore((s) => s.setNoteDraft)
  const requestPrompt = useAppStore((s) => s.requestPrompt)
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

  const handleAction = (id: string) => {
    switch (id) {
      case 'highlight':
        highlight()
        break
      case 'note':
        makeNote()
        break
      case 'explain':
        askAi('Объясни фрагмент из документа:')
        break
      case 'translate':
        setTranslation(null)
        translateMutation.mutate(selection.text)
        break
      case 'ask':
        askAi('Вопрос по фрагменту из документа:')
        break
      case 'copy':
        copy()
        break
    }
  }

  return (
    <FloatingSelectionToolbar
      actions={[
        { id: 'highlight', label: 'Highlight' },
        { id: 'note', label: 'Note' },
        { id: 'explain', label: 'Explain', accent: true },
        { id: 'translate', label: 'Translate' },
        { id: 'ask', label: 'Ask AI', accent: true },
        { id: 'copy', label: 'Copy' },
      ]}
      onAction={handleAction}
    >
      {(translateMutation.isPending || translation || translateMutation.isError) && (
        <div className="max-w-[280px] border-t border-border-glass px-2 py-1.5 text-[11px] text-text-secondary">
          {translateMutation.isPending && 'Translating…'}
          {translateMutation.isError && <span className="text-amber">Ошибка перевода</span>}
          {translation && <span className="whitespace-pre-wrap">{translation}</span>}
        </div>
      )}
    </FloatingSelectionToolbar>
  )
}
