import { useEffect, useState } from 'react'
import ChatPanel from '../chat/ChatPanel'
import { useAppStore } from '../store/appStore'
import { usePdfStore } from './pdfStore'
import { AiIcon, ChevronRightIcon } from './icons'

/**
 * Collapsible AI column inside the PDF workspace. Wraps the existing
 * ChatPanel; a pending prompt (Explain / Ask AI from the viewer) seeds the
 * chat draft via a keyed remount + initialPrompt.
 */
export default function AiPanel() {
  const aiPanelOpen = usePdfStore((s) => s.aiPanelOpen)
  const setAiPanelOpen = usePdfStore((s) => s.setAiPanelOpen)
  const pendingPrompt = usePdfStore((s) => s.pendingPrompt)
  const clearPrompt = usePdfStore((s) => s.clearPrompt)

  const aiProfiles = useAppStore((s) => s.aiProfiles)
  const selectedProfileId = useAppStore((s) => s.selectedProfileId)
  const setSelectedProfileId = useAppStore((s) => s.setSelectedProfileId)
  const loadAiProfiles = useAppStore((s) => s.loadAiProfiles)

  const [seed, setSeed] = useState<{ text: string; key: number } | null>(null)

  useEffect(() => {
    if (aiProfiles.length === 0) void loadAiProfiles()
  }, [aiProfiles.length, loadAiProfiles])

  useEffect(() => {
    if (pendingPrompt) {
      setSeed({ text: pendingPrompt, key: Date.now() })
      clearPrompt()
    }
  }, [pendingPrompt, clearPrompt])

  if (!aiPanelOpen) {
    return (
      <button
        type="button"
        onClick={() => setAiPanelOpen(true)}
        title="Open AI assistant"
        className="flex w-7 shrink-0 flex-col items-center gap-2 border-l border-border-glass bg-bg-secondary py-3 text-purple transition-colors hover:bg-bg-card"
      >
        <AiIcon className="h-4 w-4" />
        <span className="text-[10px] uppercase tracking-[0.15em] [writing-mode:vertical-rl]">
          AI
        </span>
      </button>
    )
  }

  return (
    <div className="flex h-full w-[360px] shrink-0 flex-col border-l border-border-glass bg-bg-secondary">
      <div className="flex h-10 shrink-0 items-center justify-between gap-2 border-b border-border-glass px-3">
        <span className="flex shrink-0 items-center gap-1.5 text-[12px] font-medium text-purple">
          <AiIcon className="h-3.5 w-3.5" />
          AI Assistant
        </span>
        {aiProfiles.length > 0 && (
          <select
            value={selectedProfileId}
            onChange={(e) => setSelectedProfileId(e.target.value)}
            title="AI-модель"
            className="min-w-0 flex-1 rounded border border-border-glass bg-bg-card px-1.5 py-0.5 text-[11px] text-text-secondary outline-none"
          >
            {aiProfiles.map((p) => (
              <option key={p.id} value={p.id}>
                {p.display_name}
              </option>
            ))}
          </select>
        )}
        <button
          type="button"
          onClick={() => setAiPanelOpen(false)}
          title="Collapse AI panel"
          className="rounded-md p-1 text-text-muted transition-colors hover:bg-bg-card hover:text-text-primary"
        >
          <ChevronRightIcon className="h-4 w-4" />
        </button>
      </div>
      <div className="flex min-h-0 flex-1 flex-col">
        <ChatPanel key={seed?.key ?? 'chat'} initialPrompt={seed?.text} />
      </div>
    </div>
  )
}
