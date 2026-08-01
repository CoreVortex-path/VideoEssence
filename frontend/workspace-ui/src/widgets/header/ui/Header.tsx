import { Sparkles } from 'lucide-react'

export function Header() {
  return (
    <header className="flex h-14 items-center justify-between border-b border-workspace-border bg-workspace-panel px-4">
      <div className="flex items-center gap-2">
        <Sparkles size={16} className="text-workspace-accent" />
        <strong className="text-sm">VideoEssence Workspace</strong>
      </div>
      <span className="text-xs text-slate-400">Research Mode</span>
    </header>
  )
}
