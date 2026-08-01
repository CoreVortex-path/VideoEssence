import { ChatPanel } from '@/features/chat/ui/ChatPanel'
import { Card } from '@/shared/ui/Card'

export function AIPanel() {
  return (
    <aside className="flex h-full flex-col gap-3 border-l border-workspace-border bg-workspace-panel p-3">
      <Card title="Conversations">
        <p className="text-sm text-slate-300">Conversation list will be loaded by document_id.</p>
      </Card>
      <div className="min-h-0 flex-1 overflow-auto">
        <ChatPanel />
      </div>
    </aside>
  )
}
