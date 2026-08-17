import { useAppStore } from '../store/appStore'

export default function DocumentViewer({ hideHeader = false }: { hideHeader?: boolean }) {
  const task = useAppStore((s) => s.currentTask)

  const title = task?.title ?? 'Untitled Document'
  const sourceType = task?.source_type ?? 'document'
  const text = task?.transcript ?? ''

  const label =
    sourceType === 'pdf'
      ? 'PDF'
      : sourceType === 'fb2'
        ? 'FB2'
        : 'Document'

  const paragraphs = text
    .split(/\n\s*\n/)
    .map((part) => part.trim())
    .filter(Boolean)

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden bg-bg-panel">
      {/* Document header */}
      {!hideHeader && (
        <div className="shrink-0 border-b border-border px-5 py-3">
          <div className="truncate text-[14px] font-medium text-text-primary">
            {title}
          </div>

          <div className="mt-0.5 text-[10px] uppercase tracking-[0.08em] text-text-faint">
            {label}
          </div>
        </div>
      )}

      {/* Document content */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        <article className="mx-auto max-w-[820px] px-8 py-10">
          {paragraphs.length > 0 ? (
            <div className="space-y-5">
              {paragraphs.map((paragraph, index) => (
                <p
                  key={index}
                  className="whitespace-pre-wrap text-[15px] leading-7 text-text-primary"
                >
                  {paragraph}
                </p>
              ))}
            </div>
          ) : (
            <div className="flex min-h-[300px] items-center justify-center text-[13px] text-text-faint">
              Document text is not available yet.
            </div>
          )}
        </article>
      </div>
    </div>
  )
}