import { useAppStore } from '../store/appStore'

export default function SummaryView() {
  const task = useAppStore((s) => s.currentTask)

  if (!task) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center text-[13px] text-text-faint">
        Process a video first
      </div>
    )
  }

  if (task.status === 'failed') {
    return (
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 text-[13px]">
        <p className="text-text-faint">Summary unavailable</p>
        <p className="max-w-md text-center text-amber">
          Processing failed: {task.error ?? 'Unknown error'}
        </p>
      </div>
    )
  }

  if (task.status !== 'completed') {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center text-[13px] text-text-faint">
        Summary will appear after processing…
      </div>
    )
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-4">
      <div className="text-[13px] leading-relaxed text-text-secondary">
        {task.summary ?? 'No summary generated.'}
      </div>
    </div>
  )
}