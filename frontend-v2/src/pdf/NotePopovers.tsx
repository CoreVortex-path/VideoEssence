import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createNote, deleteNote, getNotes, updateNote } from '../api/client'
import { usePdfStore } from './pdfStore'
import { CloseIcon } from './icons'

/**
 * Inline editor for a freshly placed note marker (noteDraft in pdfStore).
 * The anchor (page + position in locator space, top-left origin) is stored
 * on the note itself — no client-side coordinate hacks.
 */
export function NoteDraftEditor({ documentId }: { documentId: string }) {
  const noteDraft = usePdfStore((s) => s.noteDraft)
  const setNoteDraft = usePdfStore((s) => s.setNoteDraft)
  const queryClient = useQueryClient()
  const [text, setText] = useState('')
  const [tag, setTag] = useState('')

  const saveMutation = useMutation({
    mutationFn: () =>
      createNote(documentId, {
        text,
        tag: tag.trim() || null,
        page: noteDraft?.page ?? null,
        position: noteDraft ? [noteDraft.x, noteDraft.y] : null,
        selected_text: noteDraft?.selectedText ?? null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes', documentId] })
      setNoteDraft(null)
    },
  })

  if (!noteDraft) return null

  return (
    <div
      onMouseDown={(e) => e.stopPropagation()}
      className="flex w-[240px] flex-col gap-1.5 rounded-md border border-border-glass bg-bg-glass p-2 shadow-lg backdrop-blur-md"
    >
      <span className="text-[10px] uppercase tracking-[0.08em] text-text-faint">Note</span>
      <textarea
        autoFocus
        rows={3}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Текст заметки…"
        className="resize-none rounded border border-border-primary bg-bg-secondary px-2 py-1 text-[12px] text-text-primary outline-none placeholder:text-text-faint focus:border-accent"
      />
      <input
        value={tag}
        onChange={(e) => setTag(e.target.value)}
        placeholder="Ассоциация (тег)…"
        className="rounded border border-border-primary bg-bg-secondary px-2 py-1 text-[11px] text-text-primary outline-none placeholder:text-text-faint focus:border-accent"
      />
      {noteDraft.selectedText && (
        <div className="max-h-16 overflow-y-auto rounded bg-bg-secondary px-2 py-1 text-[11px] italic text-text-muted">
          «{noteDraft.selectedText}»
        </div>
      )}
      {saveMutation.isError && (
        <div className="text-[11px] text-amber">Не удалось сохранить заметку</div>
      )}
      <div className="flex justify-end gap-1.5">
        <button
          type="button"
          onClick={() => setNoteDraft(null)}
          className="rounded border border-border-glass px-2 py-0.5 text-[11px] text-text-muted hover:text-text-primary"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending || !text.trim()}
          className="rounded bg-accent px-2.5 py-0.5 text-[11px] text-white hover:bg-accent-hover disabled:opacity-40"
        >
          {saveMutation.isPending ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  )
}

/** Popover for an existing note marker: view / edit / delete. */
export function NoteViewPopover({
  documentId,
  noteId,
}: {
  documentId: string
  noteId: string
}) {
  const setOpenNoteId = usePdfStore((s) => s.setOpenNoteId)
  const queryClient = useQueryClient()

  const { data: notes } = useQuery({
    queryKey: ['notes', documentId],
    queryFn: () => getNotes(documentId),
  })
  const note = notes?.find((n) => n.id === noteId)

  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [tagDraft, setTagDraft] = useState('')
  useEffect(() => {
    setEditing(false)
    setDraft(note?.text ?? '')
    setTagDraft(note?.tag ?? '')
  }, [noteId, note?.text, note?.tag])

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['notes', documentId] })
  const updateMutation = useMutation({
    mutationFn: () =>
      updateNote(documentId, noteId, { text: draft, tag: tagDraft.trim() || null }),
    onSuccess: () => {
      invalidate()
      setEditing(false)
    },
  })
  const deleteMutation = useMutation({
    mutationFn: () => deleteNote(documentId, noteId),
    onSuccess: () => {
      invalidate()
      setOpenNoteId(null)
    },
  })

  return (
    <div
      onMouseDown={(e) => e.stopPropagation()}
      className="flex w-[240px] flex-col gap-1.5 rounded-md border border-border-glass bg-bg-glass p-2 shadow-lg backdrop-blur-md"
    >
      <div className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-[0.08em] text-text-faint">Note</span>
        <button
          type="button"
          onClick={() => setOpenNoteId(null)}
          className="rounded p-0.5 text-text-muted hover:bg-bg-card hover:text-text-primary"
        >
          <CloseIcon className="h-3 w-3" />
        </button>
      </div>

      {!note && <span className="text-[11px] text-text-faint">Заметка не найдена</span>}

      {note && !editing && (
        <>
          <div className="max-h-40 overflow-y-auto whitespace-pre-wrap text-[12px] text-text-secondary">
            {note.text}
          </div>
          {note.tag && (
            <span className="self-start rounded-full border border-border-glass bg-bg-card px-2 py-0.5 text-[10px] text-text-muted">
              {note.tag}
            </span>
          )}
          {note.selected_text && (
            <div className="max-h-16 overflow-y-auto rounded bg-bg-secondary px-2 py-1 text-[11px] italic text-text-muted">
              «{note.selected_text}»
            </div>
          )}
        </>
      )}
      {note && editing && (
        <>
          <textarea
            autoFocus
            rows={3}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="resize-none rounded border border-border-primary bg-bg-secondary px-2 py-1 text-[12px] text-text-primary outline-none focus:border-accent"
          />
          <input
            value={tagDraft}
            onChange={(e) => setTagDraft(e.target.value)}
            placeholder="Ассоциация (тег)…"
            className="rounded border border-border-primary bg-bg-secondary px-2 py-1 text-[11px] text-text-primary outline-none placeholder:text-text-faint focus:border-accent"
          />
        </>
      )}

      {note && (
        <div className="flex justify-end gap-1.5">
          <button
            type="button"
            onClick={() => deleteMutation.mutate()}
            disabled={deleteMutation.isPending}
            className="rounded border border-border-glass px-2 py-0.5 text-[11px] text-amber hover:border-amber disabled:opacity-40"
          >
            Delete
          </button>
          {editing ? (
            <button
              type="button"
              onClick={() => updateMutation.mutate()}
              disabled={updateMutation.isPending || !draft.trim()}
              className="rounded bg-accent px-2.5 py-0.5 text-[11px] text-white hover:bg-accent-hover disabled:opacity-40"
            >
              Save
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setEditing(true)}
              className="rounded border border-border-glass px-2 py-0.5 text-[11px] text-text-secondary hover:text-text-primary"
            >
              Edit
            </button>
          )}
        </div>
      )}
    </div>
  )
}
