import { usePdfStore } from './pdfStore'
import type { PdfTool } from './types'
import {
  EraserIcon,
  HandIcon,
  HighlightIcon,
  NoteIcon,
  PenIcon,
  RectIcon,
  SelectIcon,
  UnderlineIcon,
} from './icons'

const TOOLS: { id: PdfTool; label: string; Icon: (p: { className?: string }) => JSX.Element }[] = [
  { id: 'select', label: 'Select text', Icon: SelectIcon },
  { id: 'hand', label: 'Pan', Icon: HandIcon },
  { id: 'highlight', label: 'Highlight', Icon: HighlightIcon },
  { id: 'underline', label: 'Underline', Icon: UnderlineIcon },
  { id: 'pen', label: 'Pen', Icon: PenIcon },
  { id: 'rect', label: 'Rectangle', Icon: RectIcon },
  { id: 'note', label: 'Note', Icon: NoteIcon },
  { id: 'eraser', label: 'Eraser', Icon: EraserIcon },
]

/** Floating vertical tool pill on the left edge of the viewer. */
export default function ToolsPalette() {
  const tool = usePdfStore((s) => s.tool)
  const setTool = usePdfStore((s) => s.setTool)

  return (
    <div className="absolute left-3 top-1/2 z-20 flex -translate-y-1/2 flex-col gap-0.5 rounded-lg border border-border-glass bg-bg-glass p-1 shadow-lg backdrop-blur-md">
      {TOOLS.map(({ id, label, Icon }) => (
        <button
          key={id}
          type="button"
          onClick={() => setTool(id)}
          title={label}
          className={`rounded-md p-1.5 transition-colors ${
            tool === id
              ? 'bg-accent text-white'
              : 'text-text-muted hover:bg-bg-card hover:text-text-primary'
          }`}
        >
          <Icon className="h-4 w-4" />
        </button>
      ))}
    </div>
  )
}
