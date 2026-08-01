import { Card } from '@/shared/ui/Card'

const messages = [
  { id: 'm1', role: 'user', text: 'Summarize chapter 1 in simpler terms.' },
  { id: 'm2', role: 'assistant', text: 'Chapter 1 explains embeddings and why they improve retrieval quality.' },
]

export function ChatPanel() {
  return (
    <Card title="AI Assistant" subtitle="Conversation view (stream-ready architecture)">
      <div className="space-y-2">
        {messages.map((message) => (
          <article
            key={message.id}
            className="rounded-lg border border-workspace-border bg-workspace-muted p-3"
          >
            <p className="text-xs uppercase tracking-wide text-slate-400">{message.role}</p>
            <p className="mt-1 text-sm text-slate-100">{message.text}</p>
          </article>
        ))}
      </div>
    </Card>
  )
}
