import { useAppStore } from '../store/appStore'

export default function TopBar() {
  const task = useAppStore((s) => s.currentTask)

  return (
    <div className="flex items-center justify-between gap-3 px-4 py-2.5 bg-bg-panel border-b border-border">
      <div className="truncate text-[13px] font-medium text-text-primary">
        {task?.title ?? 'Untitled Video'}
      </div>
      <div className="shrink-0 text-[11px] text-text-faint">
        {task?.source_type === 'youtube' ? 'YouTube' : 'Local File'}
      </div>
    </div>
  )
}