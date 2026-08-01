import { useEffect, useRef } from 'react'

import type { TranslationSegment } from '@/entities/translation/model/types'
import { Card } from '@/shared/ui/Card'

interface TranslationPanelProps {
  segments: TranslationSegment[]
  activeChunkId: string | null
  autoScrollEnabled: boolean
}

export function TranslationPanel({ segments, activeChunkId, autoScrollEnabled }: TranslationPanelProps) {
  const nodeMap = useRef<Record<string, HTMLElement | null>>({})

  useEffect(() => {
    if (!autoScrollEnabled || !activeChunkId) {
      return
    }
    nodeMap.current[activeChunkId]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [activeChunkId, autoScrollEnabled])

  return (
    <Card title="Translation" subtitle="Synchronized bilingual view">
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg border border-workspace-border bg-workspace-muted p-3 text-sm text-slate-200">
          <h4 className="mb-2 text-xs uppercase tracking-wide text-slate-400">Original</h4>
          <div className="space-y-2">
            {segments.map((segment) => (
              <div
                key={segment.id}
                ref={(node) => {
                  nodeMap.current[segment.id] = node
                }}
                className={segment.id === activeChunkId ? 'rounded bg-workspace-panel p-1' : ''}
              >
                <p>{segment.sourceText}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-lg border border-workspace-border bg-workspace-muted p-3 text-sm text-slate-200">
          <h4 className="mb-2 text-xs uppercase tracking-wide text-slate-400">Translation</h4>
          <div className="space-y-2">
            {segments.map((segment) => (
              <div key={segment.id} className={segment.id === activeChunkId ? 'rounded bg-workspace-panel p-1' : ''}>
                <p>{segment.translatedText || '—'}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Card>
  )
}
