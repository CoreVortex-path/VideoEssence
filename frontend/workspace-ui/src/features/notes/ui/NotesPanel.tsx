import { Card } from '@/shared/ui/Card'

const notes = [
  { id: 'n1', text: 'Check this term later', chunk: 'chunk-2' },
  { id: 'n2', text: 'Ask AI to simplify this chapter', chunk: 'chunk-3' },
]

export function NotesPanel() {
  return (
    <Card title="Notes" subtitle="Document-scoped note workspace">
      <div className="space-y-2">
        {notes.map((note) => (
          <article key={note.id} className="rounded-lg border border-workspace-border bg-workspace-muted p-3">
            <p className="text-sm text-slate-200">{note.text}</p>
            <p className="mt-1 text-xs text-slate-400">linked to {note.chunk}</p>
          </article>
        ))}
      </div>
    </Card>
  )
}
