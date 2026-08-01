interface StatusBarProps {
  activeDocumentId: string | null
  activeTab: string
  currentTime: number
  playbackRate: number
  activeChapter: string | null
}

export function StatusBar({
  activeDocumentId,
  activeTab,
  currentTime,
  playbackRate,
  activeChapter,
}: StatusBarProps) {

  return (
    <footer className="flex h-8 items-center justify-between border-t border-workspace-border bg-workspace-panel px-3 text-xs text-slate-400">
      <span>Workspace · {activeDocumentId ?? 'no-document'} · tab: {activeTab}</span>
      <span>
        t={currentTime.toFixed(1)}s · speed={playbackRate.toFixed(2)}x · chapter={activeChapter ?? '-'}
      </span>
    </footer>
  )
}
