import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useAppStore } from '../store/appStore'
import { createNote } from '../api/client'
import type { TranscriptSegment as SegmentData } from '../api/client'
import FloatingSelectionToolbar from '../selection/FloatingSelectionToolbar'
import TranscriptSegment from './TranscriptSegment'

interface ToolbarState {
  top: number
  left: number
  text: string
  videoTime: number
}

function findActiveIndex(segments: SegmentData[], time: number): number {
  return segments.reduce((acc, seg, i) => (time >= seg.start ? i : acc), 0)
}

/** Ближайший родитель с data-segment-start (см. TranscriptSegment) — привязка выделения к таймкоду. */
function findSegmentStart(node: Node | null, container: HTMLElement): number | null {
  let el: HTMLElement | null =
    node instanceof HTMLElement ? node : (node?.parentElement ?? null)
  while (el && el !== container) {
    const v = el.dataset.segmentStart
    if (v !== undefined) {
      const n = Number(v)
      return Number.isNaN(n) ? null : n
    }
    el = el.parentElement
  }
  return null
}

export default function TranscriptView() {
  const playerTime = useAppStore((s) => s.playerTime)
  const segments = useAppStore((s) => s.transcriptSegments)
  const trans = useAppStore((s) => s.translationSegments)
  const jumpTo = useAppStore((s) => s.jumpTo)
  const docId = useAppStore((s) => s.currentDocumentId)

  const queryClient = useQueryClient()
  const containerRef = useRef<HTMLDivElement>(null)
  const activeRef = useRef<HTMLDivElement>(null)
  const [toolbar, setToolbar] = useState<ToolbarState | null>(null)
  const [openIndexes, setOpenIndexes] = useState<Set<number>>(new Set())

  const activeIndex = findActiveIndex(segments, playerTime)

  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [activeIndex])

  // Note: выделенный фрагмент транскрипта сохраняется через Notes API
  const noteMutation = useMutation({
    mutationFn: (payload: { text: string; videoTime: number }) =>
      createNote(docId!, {
        selected_text: payload.text,
        text: '',
        video_time: payload.videoTime,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notes', docId] }),
  })

  const handleSelection = () => {
    const container = containerRef.current
    const selection = window.getSelection()
    if (!container || !selection || selection.isCollapsed) {
      setToolbar(null)
      return
    }
    const text = selection.toString().trim()
    const range = selection.getRangeAt(0)
    if (!text || !container.contains(range.commonAncestorContainer)) {
      setToolbar(null)
      return
    }
    // video_time = start первого задетого сегмента; fallback — текущее время плеера
    const videoTime =
      findSegmentStart(range.startContainer, container) ??
      findSegmentStart(range.endContainer, container) ??
      playerTime
    const rect = range.getBoundingClientRect()
    const containerRect = container.getBoundingClientRect()
    setToolbar({
      top: rect.top - containerRect.top + container.scrollTop - 34,
      left: rect.left - containerRect.left + rect.width / 2 - 60,
      text,
      videoTime,
    })
  }

  const handleToolbarAction = (id: string) => {
    if (!toolbar) return
    switch (id) {
      case 'ask':
        useAppStore
          .getState()
          .requestPrompt(`Вопрос по фрагменту из транскрипта:\n\n«${toolbar.text}»`)
        break
      case 'note':
        if (docId) noteMutation.mutate({ text: toolbar.text, videoTime: toolbar.videoTime })
        break
      case 'copy':
        navigator.clipboard.writeText(toolbar.text).catch(() => undefined)
        break
    }
    setToolbar(null)
  }

  const handleTranslate = (idx: number) => {
    setOpenIndexes((prev) => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })
  }

  if (segments.length === 0) {
    const status = useAppStore.getState().currentTask?.status
    return (
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 text-[13px] text-text-faint">
        <p>Transcript will appear here after processing</p>
        {status && status !== 'completed' && (
          <p className="text-amber">Task status: {status}</p>
        )}
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className="relative min-h-0 flex-1 overflow-y-auto"
      onMouseUp={handleSelection}
      onKeyUp={handleSelection}
    >
      {toolbar && (
        <FloatingSelectionToolbar
          className="absolute z-20"
          style={{ top: toolbar.top, left: toolbar.left }}
          actions={[
            { id: 'ask', label: 'Ask AI', accent: true },
            { id: 'note', label: noteMutation.isPending ? '…' : 'Note' },
            { id: 'copy', label: 'Copy' },
          ]}
          onAction={handleToolbarAction}
        />
      )}
      <div className="divide-y divide-border-glass">
        {segments.map((seg, i) => {
          const isOpen = openIndexes.has(i)
          const inline = isOpen ? (trans[i]?.enrichment?.translation ?? null) : null

          return (
            <div key={seg.start} ref={i === activeIndex ? activeRef : undefined}>
              <TranscriptSegment
                segment={{
                  start: seg.start,
                  end: seg.end,
                  text: seg.text,
                  translation: inline,
                }}
                isActive={i === activeIndex}
                onSeek={jumpTo}
                onTranslate={() => handleTranslate(i)}
              />
            </div>
          )
        })}
      </div>
    </div>
  )
}
