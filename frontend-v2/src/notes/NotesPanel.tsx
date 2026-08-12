import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAppStore } from '../store/appStore'
import { createNote, deleteNote, getNotes, updateNote } from '../api/client'
import type { NoteResponse } from '../api/client'
import NoteItem from './NoteItem'

/** Заметки: CRUD через TanStack Query, визуальный reorder через HTML5 DnD. */
export default function NotesPanel() {
  const docId = useAppStore((s) => s.currentDocumentId)
  const queryClient = useQueryClient()

  const queryKey = ['notes', docId] as const

  const { data: notes, isLoading, isError } = useQuery({
    queryKey,
    queryFn: () => getNotes(docId!),
    enabled: docId !== null,
  })

  // Локальный порядок для визуального DnD-reorder (без API)
  const [order, setOrder] = useState<string[]>([])
  useEffect(() => {
    if (notes) setOrder(notes.map((n) => n.id))
  }, [notes])

  const invalidate = () => queryClient.invalidateQueries({ queryKey })

  const createMutation = useMutation({
    mutationFn: () => createNote(docId!, { text: '' }),
    onSuccess: invalidate,
  })
  const updateMutation = useMutation({
    mutationFn: ({ id, text }: { id: string; text: string }) =>
      updateNote(docId!, id, { text }),
    onSuccess: invalidate,
  })
  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteNote(docId!, id),
    onSuccess: invalidate,
  })

  // HTML5 drag-and-drop reorder
  const dragIdRef = useRef<string | null>(null)
  const [dragOverId, setDragOverId] = useState<string | null>(null)

  const handleDrop = () => {
    const dragId = dragIdRef.current
    if (dragId && dragOverId && dragId !== dragOverId) {
      const next = order.filter((id) => id !== dragId)
      next.splice(next.indexOf(dragOverId), 0, dragId)
      setOrder(next)
      console.log('[Notes] новый порядок:', next)
    }
    dragIdRef.current = null
    setDragOverId(null)
  }

  const byId = new Map((notes ?? []).map((n) => [n.id, n]))
  const ordered = order
    .map((id) => byId.get(id))
    .filter((n): n is NoteResponse => n !== undefined)

  if (docId === null) {
    return (
      <div className="flex flex-1 items-center justify-center p-4 text-center text-[13px] text-text-faint">
        Process a video first
      </div>
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="border-b border-border-glass p-2">
        <button
          type="button"
          onClick={() => createMutation.mutate()}
          disabled={createMutation.isPending}
          className="w-full rounded-md bg-accent px-2 py-1.5 text-[12px] text-white transition-colors hover:bg-accent-hover disabled:opacity-40"
        >
          + Add Note
        </button>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-2">
        {isLoading && <div className="text-[12px] text-text-muted">Loading...</div>}
        {isError && (
          <div className="animate-pulse rounded border border-amber/40 p-2 text-[12px] text-amber">
            Не удалось загрузить заметки
          </div>
        )}
        {ordered.map((note) => (
          <NoteItem
            key={note.id}
            note={note}
            isDragOver={dragOverId === note.id}
            onSave={(id, text) => updateMutation.mutate({ id, text })}
            onDelete={(id) => deleteMutation.mutate(id)}
            onDragStart={(id) => {
              dragIdRef.current = id
            }}
            onDragOver={setDragOverId}
            onDrop={handleDrop}
          />
        ))}
        {notes && notes.length === 0 && (
          <div className="text-[12px] text-text-faint">Заметок пока нет</div>
        )}
      </div>
    </div>
  )
}
