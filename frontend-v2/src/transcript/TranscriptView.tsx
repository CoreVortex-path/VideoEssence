import { useEffect, useRef, useState } from 'react'
import { useAppStore } from '../store/appStore'
import type { TranscriptSegment as SegmentData } from '../api/client'
import TranscriptSegment from './TranscriptSegment'
import InlineToolbar from './InlineToolbar'
import type { ToolbarPosition } from './InlineToolbar'

function findActiveIndex(segments: SegmentData[], time: number): number {
  return segments.reduce((acc, seg, i) => (time >= seg.start ? i : acc), 0)
}

export default function TranscriptView() {
  const playerTime = useAppStore((s) => s.playerTime)
  const segments = useAppStore((s) => s.transcriptSegments)
  const trans = useAppStore((s) => s.translationSegments)
  const jumpTo = useAppStore((s) => s.jumpTo)

  const containerRef = useRef<HTMLDivElement>(null)
  const activeRef = useRef<HTMLDivElement>(null)
  const [toolbar, setToolbar] = useState<ToolbarPosition | null>(null)
  const [openIndexes, setOpenIndexes] = useState<Set<number>>(new Set())

  const activeIndex = findActiveIndex(segments, playerTime)

  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [activeIndex])

  const handleSelection = () => {
    const container = containerRef.current
    const selection = window.getSelection()
    if (!container || !selection || selection.isCollapsed) {
      setToolbar(null)
      return
    }
    const range = selection.getRangeAt(0)
    if (!container.contains(range.commonAncestorContainer)) {
      setToolbar(null)
      return
    }
    const rect = range.getBoundingClientRect()
    const containerRect = container.getBoundingClientRect()
    setToolbar({
      top: rect.top - containerRect.top + container.scrollTop - 34,
      left: rect.left - containerRect.left + rect.width / 2 - 60,
    })
  }

  const handleToolbarAction = (action: 'ask-ai' | 'note' | 'highlight') => {
    console.log('[InlineToolbar]', action, window.getSelection()?.toString())
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
      {toolbar && <InlineToolbar position={toolbar} onAction={handleToolbarAction} />}
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
  )
}