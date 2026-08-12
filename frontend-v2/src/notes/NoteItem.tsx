import { useRef, useState } from 'react'
import type { NoteResponse } from '../api/client'

interface NoteItemProps {
  note: NoteResponse
  onSave: (noteId: string, text: string) => void
  onDelete: (noteId: string) => void
  onDragStart: (noteId: string) => void
  onDragOver: (noteId: string) => void
  onDrop: () => void
  isDragOver: boolean
}

/** Одна заметка: drag-handle, title (локальный), text (contentEditable), delete. */
export default function NoteItem({
  note,
  onSave,
  onDelete,
  onDragStart,
  onDragOver,
  onDrop,
  isDragOver,
}: NoteItemProps) {
  // Title в API нет — хранится локально до появления поля на бэкенде
  const [title, setTitle] = useState('New note')
  const [editingTitle, setEditingTitle] = useState(false)
  const textRef = useRef<HTMLDivElement>(null)

  return (
    <div
      draggable
      onDragStart={() => onDragStart(note.id)}
      onDragOver={(e) => {
        e.preventDefault()
        onDragOver(note.id)
      }}
      onDrop={onDrop}
      className={`rounded-md border bg-bg-card p-2 transition-colors ${
        isDragOver ? 'border-accent' : 'border-border-glass'
      }`}
    >
      <div className="flex items-center gap-1.5">
        <span
          className="cursor-grab text-text-faint select-none"
          title="Перетащить для изменения порядка"
        >
          ⋮⋮
        </span>
        {editingTitle ? (
          <input
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onBlur={() => setEditingTitle(false)}
            onKeyDown={(e) => e.key === 'Enter' && setEditingTitle(false)}
            className="flex-1 rounded border border-border-primary bg-bg-secondary px-1 text-[12px] text-text-primary outline-none"
          />
        ) : (
          <span
            onDoubleClick={() => setEditingTitle(true)}
            title="Двойной клик — редактировать"
            className="flex-1 truncate text-[12px] font-medium text-text-primary"
          >
            {title}
          </span>
        )}
        <button
          type="button"
          onClick={() => onDelete(note.id)}
          title="Удалить заметку"
          className="text-[11px] text-text-muted hover:text-amber"
        >
          ✕
        </button>
      </div>
      <div
        ref={textRef}
        contentEditable
        suppressContentEditableWarning
        onBlur={() => onSave(note.id, textRef.current?.innerText ?? '')}
        data-placeholder="Текст заметки…"
        className="mt-1 min-h-[20px] rounded px-1 text-[12px] leading-relaxed text-text-secondary outline-none empty:before:text-text-faint empty:before:content-[attr(data-placeholder)] focus:bg-bg-secondary"
      >
        {note.text}
      </div>
    </div>
  )
}
