import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAppStore } from '../store/appStore'
import {
  createAssistantConversation,
  createChatConversation,
  createNote,
  getAssistantMessages,
  getChatMessages,
  postAssistantMessage,
  postChatMessage,
} from '../api/client'
import type { ChatMessageResponse, ChatMode } from '../api/client'
import { useConversationRestore } from './useConversationRestore'

const WIDTH_ICONS = { normal: '⤢', wide: '⤡', fullscreen: '⛶' } as const

const MODE_LABELS: Record<ChatMode, string> = {
  document: 'Документ',
  library: 'Библиотека',
  general: 'Общий',
}

const MODE_HINTS: Record<ChatMode, string> = {
  document: 'Задайте вопрос по содержанию этого документа.',
  library: 'Задайте вопрос — отвечу по материалам вашей библиотеки.',
  general: 'Задайте любой вопрос — отвечу как обычный AI-ассистент.',
}

function formatTime(iso?: string | null): string {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function messageMeta(m: ChatMessageResponse): {
  sources: number
  model: string | null
} {
  const meta = (m.metadata ?? {}) as Record<string, unknown>
  const chunkIds = meta.source_chunk_ids
  const model = meta.ai_profile_name
  return {
    sources: Array.isArray(chunkIds) ? chunkIds.length : 0,
    model: typeof model === 'string' ? model : null,
  }
}

/** AI-чат: история через useQuery, отправка через useMutation. */
export default function ChatPanel({ initialPrompt }: { initialPrompt?: string }) {
  const docId = useAppStore((s) => s.currentDocumentId)
  const convId = useAppStore((s) => s.currentConversationId)
  const setConversationId = useAppStore((s) => s.setConversationId)
  const widthMode = useAppStore((s) => s.rightPanelWidthMode)
  const toggleWidth = useAppStore((s) => s.toggleRightPanelWidth)
  const selectedProfileId = useAppStore((s) => s.selectedProfileId)
  const chatMode = useAppStore((s) => s.chatMode)
  const setChatMode = useAppStore((s) => s.setChatMode)

  // Без загруженного документа режим «Документ» недоступен.
  const mode: ChatMode = docId === null && chatMode === 'document' ? 'library' : chatMode
  const isDocumentMode = mode === 'document'

  const queryClient = useQueryClient()
  // initialPrompt сидит черновик при монтировании (PDF workspace: Explain / Ask AI)
  const [draft, setDraft] = useState(initialPrompt ?? '')
  const [noteBtn, setNoteBtn] = useState<{ top: number; left: number; text: string } | null>(
    null,
  )
  const listRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const keywords = useAppStore((s) => s.currentTask?.keywords) ?? []
  const suggestedQuestions = useAppStore((s) => s.currentTask?.suggested_questions) ?? []

  useConversationRestore(docId, isDocumentMode)

  // Диалоги режимов не пересекаются: скоуп в ключе запроса.
  const scope = isDocumentMode ? docId : 'assistant'
  const queryKey = ['chat-messages', scope, convId] as const

  const { data: messages, isLoading, isError } = useQuery({
    queryKey,
    queryFn: () =>
      isDocumentMode ? getChatMessages(docId!, convId!) : getAssistantMessages(convId!),
    enabled: convId !== null && (isDocumentMode ? docId !== null : true),
  })

  const sendMutation = useMutation({
    mutationFn: async (content: string) => {
      let cid = convId
      if (!cid) {
        // Первое сообщение: создаём conversation в нужном скоупе
        const conv = isDocumentMode
          ? await createChatConversation(docId!)
          : await createAssistantConversation()
        cid = conv.id
        setConversationId(cid)
      }
      return isDocumentMode
        ? postChatMessage(docId!, cid, content, selectedProfileId)
        : postAssistantMessage(cid, content, mode, selectedProfileId)
    },
    onSuccess: (res) => {
      queryClient.setQueryData<ChatMessageResponse[]>(
        ['chat-messages', scope, res.conversation_id],
        (old) => [...(old ?? []), res.user_message, res.assistant_message],
      )
    },
  })

  // «→ в заметку»: выделенный текст сообщения сохраняется через Notes API
  const noteMutation = useMutation({
    mutationFn: (text: string) => createNote(docId!, { text }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes', docId] })
      setNoteBtn(null)
      window.getSelection()?.removeAllRanges()
    },
  })

  // Паттерн InlineToolbar из TranscriptView: плавающая кнопка над выделением.
  const handleSelection = () => {
    const container = listRef.current
    const selection = window.getSelection()
    if (!container || !selection || selection.isCollapsed || docId === null) {
      setNoteBtn(null)
      return
    }
    const text = selection.toString().trim()
    const range = selection.getRangeAt(0)
    if (!text || !container.contains(range.commonAncestorContainer)) {
      setNoteBtn(null)
      return
    }
    const rect = range.getBoundingClientRect()
    const containerRect = container.getBoundingClientRect()
    setNoteBtn({
      top: rect.top - containerRect.top + container.scrollTop - 30,
      left: rect.left - containerRect.left + rect.width / 2 - 40,
      text,
    })
  }

  // Автоскролл вниз при новых сообщениях / индикаторе печати
  useEffect(() => {
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages?.length, sendMutation.isPending])

  // Смена документа/диалога сбрасывает плавающую кнопку
  useEffect(() => setNoteBtn(null), [docId, convId])

  const switchMode = (next: ChatMode) => {
    if (next === mode) return
    setChatMode(next)
    setConversationId(null)
  }

  const sendContent = (content: string) => {
    const text = content.trim()
    if (!text || sendMutation.isPending) return
    setDraft('')
    sendMutation.mutate(text)
  }

  const send = () => sendContent(draft)

  const insertKeyword = (kw: string) => {
    setDraft(`Расскажи подробнее про ${kw}`)
    inputRef.current?.focus()
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  const isEmpty = !isLoading && (messages?.length ?? 0) === 0

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-border-glass px-2 py-1">
        <div className="flex overflow-hidden rounded-md border border-border-glass">
          {(Object.keys(MODE_LABELS) as ChatMode[]).map((m) => {
            const disabled = m === 'document' && docId === null
            return (
              <button
                key={m}
                type="button"
                onClick={() => switchMode(m)}
                disabled={disabled}
                title={disabled ? 'Сначала обработайте видео' : MODE_HINTS[m]}
                className={`px-2 py-1 text-[11px] transition-colors ${
                  mode === m
                    ? 'bg-accent text-white'
                    : 'text-text-muted hover:bg-bg-card hover:text-text-secondary'
                } disabled:cursor-not-allowed disabled:opacity-40`}
              >
                {MODE_LABELS[m]}
              </button>
            )
          })}
        </div>
        <button
          type="button"
          onClick={toggleWidth}
          title={`Ширина панели: ${widthMode}`}
          className="rounded px-1.5 py-0.5 text-[13px] text-text-muted hover:bg-bg-card hover:text-text-primary"
        >
          {WIDTH_ICONS[widthMode]}
        </button>
      </div>

      <div
        ref={listRef}
        className="relative flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-3"
        onMouseUp={handleSelection}
        onKeyUp={handleSelection}
      >
        {noteBtn && (
          <button
            type="button"
            // onMouseDown, чтобы клик не сбрасывал выделение до обработки
            onMouseDown={(e) => {
              e.preventDefault()
              noteMutation.mutate(noteBtn.text)
            }}
            disabled={noteMutation.isPending}
            title="Сохранить выделенное в заметку"
            className="glass-panel absolute z-20 rounded-md border px-2 py-0.5 text-[11px] text-text-secondary shadow-lg transition-colors hover:text-accent disabled:opacity-50"
            style={{ top: noteBtn.top, left: noteBtn.left }}
          >
            {noteMutation.isPending ? '…' : '→ в заметку'}
          </button>
        )}
        {isEmpty && (
          <div className="flex flex-col gap-3">
            <div className="pt-2 text-center">
              <div className="text-[13px] font-medium text-text-primary">
                Привет! Я ваш AI-помощник.
              </div>
              <div className="mt-1 text-[12px] text-text-faint">{MODE_HINTS[mode]}</div>
            </div>
            {isDocumentMode && keywords.length > 0 && (
              <div className="flex flex-wrap justify-center gap-1.5">
                {keywords.map((kw) => (
                  <button
                    key={kw}
                    type="button"
                    onClick={() => insertKeyword(kw)}
                    title={`Расскажи подробнее про ${kw}`}
                    className="rounded-full border border-border-glass bg-bg-card px-2.5 py-1 text-[12px] text-text-secondary transition-colors hover:border-accent hover:text-text-primary"
                  >
                    {kw}
                  </button>
                ))}
              </div>
            )}
            {isDocumentMode && suggestedQuestions.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <div className="text-[12px] text-text-faint">Или задайте один из вопросов:</div>
                {suggestedQuestions.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => sendContent(q)}
                    disabled={sendMutation.isPending}
                    className="flex items-center justify-between gap-2 rounded-lg border border-border-glass bg-bg-card px-3 py-2 text-left text-[12px] text-text-secondary transition-colors hover:border-accent hover:text-text-primary disabled:opacity-40"
                  >
                    <span>{q}</span>
                    <span className="shrink-0 text-text-faint">→</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
        {isLoading && <div className="text-[12px] text-text-muted">Loading...</div>}
        {isError && (
          <div className="animate-pulse rounded border border-amber/40 p-2 text-[12px] text-amber">
            Не удалось загрузить сообщения
          </div>
        )}
        {messages?.map((m) => {
          const meta = m.role === 'assistant' ? messageMeta(m) : null
          const time = formatTime(m.created_at)
          return (
            <div
              key={m.id}
              className={
                m.role === 'user'
                  ? 'max-w-[85%] self-end rounded-lg bg-gradient-to-br from-accent to-cyan px-3 py-1.5 text-[13px] text-white'
                  : 'max-w-[85%] self-start rounded-lg border border-border-glass bg-bg-card px-3 py-1.5 text-[13px] text-text-secondary'
              }
            >
              <div className="whitespace-pre-wrap">{m.content}</div>
              {meta && meta.sources > 0 && (
                <div className="mt-1 text-[11px] text-text-faint">
                  Источники ({meta.sources})
                </div>
              )}
              {(time || meta?.model) && (
                <div
                  className={`mt-0.5 flex items-center gap-2 text-[10px] ${
                    m.role === 'user' ? 'justify-end text-white/70' : 'text-text-faint'
                  }`}
                >
                  {meta?.model && <span>✦ {meta.model}</span>}
                  {time && <span>{time}</span>}
                </div>
              )}
            </div>
          )
        })}
        {sendMutation.isPending && (
          <div className="flex gap-1 self-start rounded-lg border border-border-glass bg-bg-card px-3 py-2">
            <span className="typing-dot" />
            <span className="typing-dot" />
            <span className="typing-dot" />
          </div>
        )}
        {sendMutation.isError && (
          <div className="animate-pulse rounded border border-amber/40 p-2 text-[12px] text-amber">
            Сообщение не отправлено: {sendMutation.error?.message}
          </div>
        )}
      </div>

      <div className="flex items-end gap-2 border-t border-border-glass p-2">
        <textarea
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          rows={2}
          placeholder="Ask about the video… (Enter — отправить)"
          className="min-h-[36px] flex-1 resize-none rounded-md border border-border-primary bg-bg-secondary px-2 py-1.5 text-[13px] text-text-primary outline-none placeholder:text-text-faint focus:border-accent"
        />
        <button
          type="button"
          onClick={send}
          disabled={sendMutation.isPending || !draft.trim()}
          className="rounded-md bg-accent px-3 py-1.5 text-[13px] text-white transition-colors hover:bg-accent-hover disabled:opacity-40"
        >
          ➤
        </button>
      </div>
    </div>
  )
}
