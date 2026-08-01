import type { ChapterItem } from '@/entities/chapter/model/types'
import type { SummaryData } from '@/entities/summary/model/types'
import { Button } from '@/shared/ui/Button'
import { Card } from '@/shared/ui/Card'
import { formatSeconds } from '@/shared/utils/time'

interface SummaryPanelProps {
  summary: SummaryData | null
  chapters: ChapterItem[]
  onJumpToChapter: (seconds: number, chapterId: string) => void
}

export function SummaryPanel({ summary, chapters, onJumpToChapter }: SummaryPanelProps) {
  return (
    <Card title="Summary" subtitle="Overview + chapter map">
      <div className="grid gap-3">
        <article className="rounded-lg border border-workspace-border bg-workspace-muted p-3">
          <h4 className="mb-1 text-sm font-semibold">Overview</h4>
          <p className="text-sm text-slate-300">{summary?.overview || 'No summary available.'}</p>
        </article>
        <article className="rounded-lg border border-workspace-border bg-workspace-muted p-3">
          <h4 className="mb-2 text-sm font-semibold">Chapters</h4>
          <div className="space-y-2">
            {chapters.map((chapter) => (
              <div key={chapter.id} className="rounded border border-workspace-border p-2">
                <p className="text-sm font-medium text-slate-100">{chapter.title}</p>
                <p className="text-xs text-slate-400">{chapter.summary}</p>
                <Button
                  className="mt-2"
                  variant="ghost"
                  onClick={() => onJumpToChapter(chapter.start, chapter.id)}
                >
                  Jump to {formatSeconds(chapter.start)}
                </Button>
              </div>
            ))}
          </div>
        </article>
      </div>
    </Card>
  )
}
