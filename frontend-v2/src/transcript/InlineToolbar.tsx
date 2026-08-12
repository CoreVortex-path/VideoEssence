export interface ToolbarPosition {
  top: number
  left: number
}

interface InlineToolbarProps {
  position: ToolbarPosition
  onAction: (action: 'ask-ai' | 'note' | 'highlight') => void
}

const ACTIONS = [
  { id: 'ask-ai', label: 'Ask AI' },
  { id: 'note', label: 'Note' },
  { id: 'highlight', label: 'Highlight' },
] as const

/** Плавающий тулбар при выделении текста (позиция absolute внутри TranscriptView). */
export default function InlineToolbar({ position, onAction }: InlineToolbarProps) {
  return (
    <div
      className="glass-panel absolute z-20 flex gap-1 rounded-md border p-1 shadow-lg"
      style={{ top: position.top, left: position.left }}
    >
      {ACTIONS.map((a) => (
        <button
          key={a.id}
          type="button"
          // onMouseDown, чтобы клик не сбрасывал выделение до обработки
          onMouseDown={(e) => {
            e.preventDefault()
            onAction(a.id)
          }}
          className="rounded px-2 py-0.5 text-[11px] text-text-secondary transition-colors hover:bg-bg-card hover:text-accent"
        >
          {a.label}
        </button>
      ))}
    </div>
  )
}
