import { useRef, useState } from 'react'
import type { NoteResponse } from '../api/client'
import { CloseIcon } from '../pdf/icons'
import { formatDate, formatTimecode } from './format'

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
      className={`rounded-md border bg-bg-card p-3 transition-colors ${
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
            className="t-body flex-1 rounded border border-border-primary bg-bg-secondary px-1 outline-none"
          />
        ) : (
          <span
            onDoubleClick={() => setEditingTitle(true)}
            title="Двойной клик — редактировать"
            className="t-card-title flex-1 truncate"
          >
            {title}
          </span>
        )}
        <button
          type="button"
          onClick={() => onDelete(note.id)}
          title="Удалить заметку"
          className="flex h-6 w-6 items-center justify-center rounded text-text-muted hover:text-amber"
        >
          <CloseIcon className="h-4 w-4" />
        </button>
      </div>
      <div
        ref={textRef}
        contentEditable
        suppressContentEditableWarning
        onBlur={() => onSave(note.id, textRef.current?.innerText ?? '')}
        data-placeholder="Текст заметки…"
        className="t-body mt-1 min-h-[20px] rounded px-1 leading-relaxed outline-none empty:before:text-text-faint empty:before:content-[attr(data-placeholder)] focus:bg-bg-secondary"
      >
        {note.text}
      </div>
      {note.selected_text && (
        <div className="mt-1 line-clamp-2 rounded border-l-[3px] border-accent/40 bg-bg-secondary py-1 pl-3 pr-2 text-[13px] italic leading-normal text-text-secondary">
          «{note.selected_text}»
        </div>
      )}
      {(note.tag || note.page != null || note.video_time != null || note.created_at) && (
        <div className="t-meta mt-1 flex flex-wrap items-center gap-1.5 px-1 text-text-muted">
          {note.tag && (
            <span className="rounded-full border border-border-glass bg-bg-secondary px-1.5 py-px text-text-muted">
              {note.tag}
            </span>
          )}
          {note.page != null && <span>стр. {note.page}</span>}
          {note.video_time != null && <span>{formatTimecode(note.video_time)}</span>}
          {note.created_at && <span>{formatDate(note.created_at)}</span>}
        </div>
      )}
    </div>
  )
}
