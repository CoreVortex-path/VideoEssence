import { useEffect, useMemo, useRef } from 'react'

import type { TranscriptSegment } from '@/entities/transcript/model/types'
import { Button } from '@/shared/ui/Button'
import { Card } from '@/shared/ui/Card'

interface TranscriptPanelProps {
  segments: TranscriptSegment[]
  activeChunkId: string | null
  autoScrollEnabled: boolean
  onSelectChunk: (chunkId: string, start: number, end: number) => void
}

export function TranscriptPanel({ segments, activeChunkId, autoScrollEnabled, onSelectChunk }: TranscriptPanelProps) {
  const nodeMap = useRef<Record<string, HTMLElement | null>>({})

  useEffect(() => {
    if (!autoScrollEnabled || !activeChunkId) {
      return
    }
    const node = nodeMap.current[activeChunkId]
    node?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [activeChunkId, autoScrollEnabled])

  const content = useMemo(() => {
    if (segments.length === 0) {
      return <p className="text-sm text-slate-400">No transcript available for this document yet.</p>
    }

    return (
      <div className="space-y-3">
        {segments.map((segment) => {
          const isActive = segment.id === activeChunkId
          return (
            <article
              key={segment.id}
              ref={(node) => {
                nodeMap.current[segment.id] = node
              }}
              className={[
                'rounded-lg border p-3',
                isActive
                  ? 'border-workspace-accent bg-workspace-muted'
                  : 'border-workspace-border bg-workspace-muted/70',
              ].join(' ')}
            >
              <button
                className="mb-2 text-xs font-semibold text-workspace-accent"
                onClick={() => onSelectChunk(segment.id, segment.start, segment.end)}
              >
                {segment.timestampLabel}
              </button>
              <p className="mb-3 text-sm text-slate-200">{segment.text}</p>
              <div className="flex flex-wrap gap-2">
                <Button variant="ghost">Translate</Button>
                <Button variant="ghost">Explain</Button>
                <Button variant="ghost">Note</Button>
                <Button variant="ghost">Highlight</Button>
                <Button variant="ghost">Ask AI</Button>
              </div>
            </article>
          )
        })}
      </div>
    )
  }, [activeChunkId, onSelectChunk, segments])

  return <Card title="Transcript">{content}</Card>
}
