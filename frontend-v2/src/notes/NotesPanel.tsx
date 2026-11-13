import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAppStore } from '../store/appStore'
import {
  createGlobalNote,
  createNote,
  deleteGlobalNote,
  deleteNote,
  getNotes,
  listDocuments,
  listGlobalNotes,
  updateGlobalNote,
  updateNote,
} from '../api/client'
import type { GlobalNotesQuery, NoteResponse } from '../api/client'
import { useDocumentTitle } from '../library/useDocumentTitle'
import { formatDate, formatTimecode } from './format'
import NoteItem from './NoteItem'

type Scope = 'document' | 'global'

const SORT_OPTIONS: { value: NonNullable<GlobalNotesQuery['sort']>; label: string }[] = [
  { value: 'updated_at_desc', label: 'Обновлены ↓' },
  { value: 'created_at_desc', label: 'Созданы ↓' },
  { value: 'created_at_asc', label: 'Созданы ↑' },
  { value: 'tag_asc', label: 'Тег' },
  { value: 'document_id', label: 'Документ' },
]

/** Название документа для фильтра/строки заметки (listDocuments title не отдаёт). */
function DocTitle({ documentId }: { documentId: string }) {
  const title = useDocumentTitle(documentId)
  return <>{title ?? `${documentId.slice(0, 8)}…`}</>
}

/** Одна строка глобальной заметки: текст, метки, навигация по клику. */
function GlobalNoteRow({
  note,
  expanded,
  onToggle,
}: {
  note: NoteResponse
  expanded: boolean
  onToggle: () => void
}) {
  const queryClient = useQueryClient()
  const openDocument = useAppStore((s) => s.openDocument)
  const jumpTo = useAppStore((s) => s.jumpTo)
  const setPendingNoteAnchor = useAppStore((s) => s.setPendingNoteAnchor)
  const currentDocumentId = useAppStore((s) => s.currentDocumentId)

  const [draft, setDraft] = useState(note.text)
  const [tagDraft, setTagDraft] = useState(note.tag ?? '')
  useEffect(() => {
    setDraft(note.text)
    setTagDraft(note.tag ?? '')
  }, [note.text, note.tag])

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['global-notes'] })
  const updateMutation = useMutation({
    mutationFn: () => updateGlobalNote(note.id, { text: draft, tag: tagDraft.trim() || null }),
    onSuccess: invalidate,
  })
  const deleteMutation = useMutation({
    mutationFn: () => deleteGlobalNote(note.id),
    onSuccess: invalidate,
  })

  // Навигационный контракт: doc+page → документ + страница + фокус заметки;
  // doc+video_time → документ + перемотка плеера; только doc → открыть документ;
  // без doc → просто раскрыть в панели.
  const navigate = () => {
    if (note.document_id && note.page != null) {
      setPendingNoteAnchor({
        noteId: note.id,
        documentId: note.document_id,
        page: note.page,
        position: note.position ?? null,
      })
      if (note.document_id !== currentDocumentId) void openDocument(note.document_id)
    } else if (note.document_id && note.video_time != null) {
      // jumpTo после openDocument: openDocument сбрасывает seekRequest,
      // плеер подхватит seekRequest при монтировании.
      const documentId = note.document_id
      const videoTime = note.video_time
      void (async () => {
        if (documentId !== currentDocumentId) await openDocument(documentId)
        jumpTo(videoTime)
      })()
    } else if (note.document_id) {
      if (note.document_id !== currentDocumentId) void openDocument(note.document_id)
    } else {
      onToggle()
    }
  }

  return (
    <div className="rounded-md border border-border-glass bg-bg-card p-3">
      <div
        role="button"
        tabIndex={0}
        onClick={navigate}
        onKeyDown={(e) => e.key === 'Enter' && navigate()}
        className="cursor-pointer"
        title={
          note.document_id
            ? note.page != null
              ? 'Открыть документ на этой странице'
              : note.video_time != null
                ? 'Открыть документ на этом таймкоде'
                : 'Открыть документ'
            : 'Раскрыть заметку'
        }
      >
        <div className="t-body line-clamp-2 leading-relaxed">
          {note.text}
        </div>
        {note.selected_text && (
          <div className="mt-1 line-clamp-2 rounded border-l-[3px] border-accent/40 bg-bg-secondary py-1 pl-3 pr-2 text-[13px] italic leading-normal text-text-secondary">
            «{note.selected_text}»
          </div>
        )}
        <div className="t-meta mt-1 flex flex-wrap items-center gap-1.5 text-text-muted">
          {note.tag && (
            <span className="rounded-full border border-border-glass bg-bg-secondary px-1.5 py-px text-text-muted">
              {note.tag}
            </span>
          )}
          {note.document_id && (
            <span className="truncate text-text-muted">
              <DocTitle documentId={note.document_id} />
            </span>
          )}
          {note.page != null && <span>стр. {note.page}</span>}
          {note.video_time != null && <span>{formatTimecode(note.video_time)}</span>}
          {note.created_at && <span>{formatDate(note.created_at)}</span>}
        </div>
      </div>

      {expanded && (
        <div className="mt-2 flex flex-col gap-1.5 border-t border-border-glass pt-2">
          <textarea
            rows={3}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="t-body resize-none rounded border border-border-primary bg-bg-secondary px-2 py-1 outline-none focus:border-accent"
          />
          <input
            value={tagDraft}
            onChange={(e) => setTagDraft(e.target.value)}
            placeholder="Ассоциация (тег)…"
            className="t-body rounded border border-border-primary bg-bg-secondary px-2 py-1 outline-none placeholder:text-text-faint focus:border-accent"
          />
          <div className="flex justify-end gap-1.5">
            <button
              type="button"
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
              className="rounded border border-border-glass px-2 py-0.5 text-[11px] text-amber hover:border-amber disabled:opacity-40"
            >
              Delete
            </button>
            <button
              type="button"
              onClick={() => updateMutation.mutate()}
              disabled={updateMutation.isPending || !draft.trim()}
              className="rounded bg-accent px-2.5 py-0.5 text-[11px] text-white hover:bg-accent-hover disabled:opacity-40"
            >
              Save
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

/** Глобальная память заметок: фильтры backend-side, клик → навигация. */
function GlobalNotesView() {
  const queryClient = useQueryClient()
  const [tag, setTag] = useState('')
  const [documentId, setDocumentId] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [sort, setSort] = useState<NonNullable<GlobalNotesQuery['sort']>>('updated_at_desc')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const params: GlobalNotesQuery = {
    tag: tag || undefined,
    document_id: documentId || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    sort,
  }

  const { data: notes, isLoading, isError } = useQuery({
    queryKey: ['global-notes', params],
    queryFn: () => listGlobalNotes(params),
  })
  const { data: documents } = useQuery({
    queryKey: ['documents'],
    queryFn: listDocuments,
  })

  const createMutation = useMutation({
    mutationFn: () => createGlobalNote({ text: 'Новая заметка' }),
    onSuccess: (note) => {
      queryClient.invalidateQueries({ queryKey: ['global-notes'] })
      setExpandedId(note.id)
    },
  })

  const inputCls =
    'rounded border border-border-primary bg-bg-secondary px-1.5 py-1.5 text-[13px] outline-none placeholder:text-text-faint focus:border-accent'

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-col gap-1.5 border-b border-border-glass p-2">
        <button
          type="button"
          onClick={() => createMutation.mutate()}
          disabled={createMutation.isPending}
          className="w-full rounded-md bg-accent px-2 py-1.5 text-[12px] text-white transition-colors hover:bg-accent-hover disabled:opacity-40"
        >
          + Add Note
        </button>
        <div className="flex gap-1.5">
          <input
            value={tag}
            onChange={(e) => setTag(e.target.value)}
            placeholder="Тег…"
            className={`${inputCls} min-w-0 flex-1`}
          />
          <select
            value={documentId}
            onChange={(e) => setDocumentId(e.target.value)}
            className={`${inputCls} min-w-0 flex-1`}
          >
            <option value="">Все документы</option>
            {(documents ?? []).map((d) => (
              <option key={d.document_id} value={d.document_id}>
                {d.document_id.slice(0, 8)}…
              </option>
            ))}
          </select>
        </div>
        <div className="flex gap-1.5">
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className={`${inputCls} min-w-0 flex-1`}
          />
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className={`${inputCls} min-w-0 flex-1`}
          />
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as typeof sort)}
            title="Сортировка"
            className={`${inputCls} shrink-0`}
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-2">
        {isLoading && <div className="t-meta">Loading...</div>}
        {isError && (
          <div className="animate-pulse rounded border border-amber/40 p-2 text-[12px] text-amber">
            Не удалось загрузить заметки
          </div>
        )}
        {(notes ?? []).map((note) => (
          <GlobalNoteRow
            key={note.id}
            note={note}
            expanded={expandedId === note.id}
            onToggle={() => setExpandedId(expandedId === note.id ? null : note.id)}
          />
        ))}
        {notes && notes.length === 0 && (
          <div className="t-meta">Заметок пока нет</div>
        )}
      </div>
    </div>
  )
}

/** Заметки: «Документ» — CRUD текущего документа; «Все» — глобальная память. */
export default function NotesPanel() {
  const docId = useAppStore((s) => s.currentDocumentId)
  const queryClient = useQueryClient()
  const [scope, setScope] = useState<Scope>('document')

  const queryKey = ['notes', docId] as const

  const { data: notes, isLoading, isError } = useQuery({
    queryKey,
    queryFn: () => getNotes(docId!),
    enabled: docId !== null && scope === 'document',
  })

  // Локальный порядок для визуального DnD-reorder (без API)
  const [order, setOrder] = useState<string[]>([])
  useEffect(() => {
    if (notes) setOrder(notes.map((n) => n.id))
  }, [notes])

  const invalidate = () => queryClient.invalidateQueries({ queryKey })

  const createMutation = useMutation({
    mutationFn: () => createNote(docId!, { text: 'Новая заметка' }),
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
    }
    dragIdRef.current = null
    setDragOverId(null)
  }

  const byId = new Map((notes ?? []).map((n) => [n.id, n]))
  const ordered = order
    .map((id) => byId.get(id))
    .filter((n): n is NoteResponse => n !== undefined)

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex border-b border-border-glass">
        {(['document', 'global'] as const).map((id) => (
          <button
            key={id}
            type="button"
            onClick={() => setScope(id)}
            className={`t-meta px-3 py-2 transition-colors ${
              scope === id
                ? 'border-b-2 border-accent text-text-primary'
                : 'text-text-muted hover:text-text-secondary'
            }`}
          >
            {id === 'document' ? 'Документ' : 'Все'}
          </button>
        ))}
      </div>

      {scope === 'global' && <GlobalNotesView />}

      {scope === 'document' &&
        (docId === null ? (
          <div className="t-caption flex flex-1 items-center justify-center p-4 text-center">
            Process a video first
          </div>
        ) : (
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
              {isLoading && <div className="t-meta">Loading...</div>}
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
                <div className="t-meta">Заметок пока нет</div>
              )}
            </div>
          </div>
        ))}
    </div>
  )
}
