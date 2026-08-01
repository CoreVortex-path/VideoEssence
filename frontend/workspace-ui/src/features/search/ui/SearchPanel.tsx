import { Card } from '@/shared/ui/Card'

const results = [
  { id: 'r1', source: 'transcript', hit: 'vector embeddings', chunk: 'chunk-1' },
  { id: 'r2', source: 'translation', hit: 'исходного материала', chunk: 'chunk-2' },
  { id: 'r3', source: 'note', hit: 'simplify this chapter', chunk: 'chunk-3' },
]

export function SearchPanel() {
  return (
    <Card title="Search" subtitle="Transcript + translation + notes">
      <div className="space-y-2">
        {results.map((result) => (
          <article key={result.id} className="rounded-lg border border-workspace-border bg-workspace-muted p-3">
            <p className="text-sm text-slate-100">{result.hit}</p>
            <p className="text-xs text-slate-400">
              {result.source} · {result.chunk}
            </p>
          </article>
        ))}
      </div>
    </Card>
  )
}
