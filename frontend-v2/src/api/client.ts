import type { components } from './v1'

export type TaskStatusResponse = components['schemas']['TaskStatusResponse']
export type ProcessMediaResponse = components['schemas']['ProcessMediaResponse']
export type ChatConversationResponse = components['schemas']['ChatConversationResponse']
export type ChatMessageResponse = components['schemas']['ChatMessageResponse']
export type TranscriptSegment = components['schemas']['TranscriptSegment']
export type TranslateTranscriptResponse = components['schemas']['TranslateTranscriptResponse']
export type SendChatMessageResponse = components['schemas']['SendChatMessageResponse']
export type NoteResponse = components['schemas']['NoteResponse']
export type NoteCreateRequest = components['schemas']['NoteCreateRequest']
export type NoteUpdateRequest = components['schemas']['NoteUpdateRequest']
export type KnowledgeGraphResponse = components['schemas']['KnowledgeGraphResponse']
export type DocumentListItemResponse = components['schemas']['DocumentListItemResponse']
export type DocumentUpdateRequest = components['schemas']['DocumentUpdateRequest']
export type DocumentUpdateResponse = components['schemas']['DocumentUpdateResponse']

/** Профиль AI-модели с GET /videos/ai-profiles (ручной тип — в OpenAPI-схеме его нет). */
export interface AIProfile {
  id: string
  display_name: string
  provider: string
  model: string
}

/** Режим AI-чата: по документу, по всей библиотеке или общий ассистент. */
export type ChatMode = 'document' | 'library' | 'general'

export interface AIProfilesResponse {
  default_profile: string
  profiles: AIProfile[]
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

/** URL стриминга медиа документа (для <video src>). */
export function getDocumentMediaUrl(docId: string) {
  return `${BASE_URL}/videos/documents/${docId}/media`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...(init?.body instanceof FormData
      ? {}
      : { headers: { 'Content-Type': 'application/json' } }),
    ...init,
  })
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export function getVideoStatus(taskId: string) {
  return request<TaskStatusResponse>(`/videos/status/${taskId}`)
}

export function listDocuments() {
  return request<DocumentListItemResponse[]>('/videos/documents')
}

export function getDocumentSnapshot(documentId: string) {
  return request<TaskStatusResponse>(`/videos/documents/${documentId}`)
}

/** Удаление документа: запись, связанные данные и файлы на диске. */
export function deleteDocument(documentId: string) {
  return request<void>(`/videos/documents/${documentId}`, { method: 'DELETE' })
}

/** Обновление документа: pin/unpin и/или переименование (PATCH, оба поля опциональны). */
export function updateDocument(documentId: string, data: DocumentUpdateRequest) {
  return request<DocumentUpdateResponse>(`/videos/documents/${documentId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export function getAiProfiles() {
  return request<AIProfilesResponse>('/videos/ai-profiles')
}

export function processMediaFile(file: File, aiProfile?: string) {
  const form = new FormData()
  form.append('file', file)
  if (aiProfile) form.append('ai_profile', aiProfile)
  return request<ProcessMediaResponse>('/videos/process-file', {
    method: 'POST',
    body: form,
  })
}

export function processMediaUrl(url: string, aiProfile?: string) {
  return request<ProcessMediaResponse>('/videos/process-url', {
    method: 'POST',
    body: JSON.stringify({ url, ai_profile: aiProfile }),
  })
}

export function translateTranscript(taskId: string, targetLanguage = 'ru', aiProfile?: string) {
  return request<TranslateTranscriptResponse>(`/videos/status/${taskId}/translate`, {
    method: 'POST',
    body: JSON.stringify({ target_language: targetLanguage, ai_profile: aiProfile }),
  })
}

/** Ручной импорт внешнего перевода: N строк 1:1 на сегменты транскрипта. */
/** Ручной импорт внешнего перевода: сплошной текст, бэкенд сам разобьёт на сегменты. */
export function importTranslation(
  taskId: string,
  targetLanguage: string,
  text: string,
) {
  return request<{
    task_id: string
    target_language: string
    transcript_segments: TranscriptSegment[]
    full_translation?: string
  }>(`/videos/status/${taskId}/translation-import`, {
    method: 'POST',
    body: JSON.stringify({
      target_language: targetLanguage,
      text,
    }),
  })
}

/** Перевод произвольного текста (inline в транскрипте). */
export function translateText(text: string, targetLanguage = 'ru', aiProfile?: string) {
  return request<{ translation: string }>('/translate', {
    method: 'POST',
    body: JSON.stringify({ text, target_language: targetLanguage, ai_profile: aiProfile }),
  })
}

export function createChatConversation(docId: string, title?: string) {
  return request<ChatConversationResponse>(
    `/documents/${docId}/chat/conversations`,
    { method: 'POST', body: JSON.stringify({ title: title ?? null }) },
  )
}

export function listChatConversations(docId: string) {
  return request<ChatConversationResponse[]>(
    `/documents/${docId}/chat/conversations`,
  )
}

export function getChatMessages(docId: string, convId: string) {
  return request<ChatMessageResponse[]>(
    `/documents/${docId}/chat/conversations/${convId}/messages`,
  )
}

export function postChatMessage(docId: string, convId: string, content: string, aiProfile?: string) {
  return request<SendChatMessageResponse>(
    `/documents/${docId}/chat/conversations/${convId}/messages`,
    { method: 'POST', body: JSON.stringify({ message: content, ai_profile: aiProfile }) },
  )
}

/** Глобальный ассистент (режимы library/general, без привязки к документу). */
export function createAssistantConversation(title?: string) {
  return request<ChatConversationResponse>('/assistant/conversations', {
    method: 'POST',
    body: JSON.stringify({ title: title ?? null }),
  })
}

export function listAssistantConversations() {
  return request<ChatConversationResponse[]>('/assistant/conversations')
}

export function getAssistantMessages(convId: string) {
  return request<ChatMessageResponse[]>(`/assistant/conversations/${convId}/messages`)
}

export function postAssistantMessage(
  convId: string,
  content: string,
  mode: Exclude<ChatMode, 'document'>,
  aiProfile?: string,
) {
  return request<SendChatMessageResponse>(`/assistant/conversations/${convId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ message: content, mode, ai_profile: aiProfile }),
  })
}

export function getNotes(docId: string) {
  return request<NoteResponse[]>(`/documents/${docId}/notes`)
}

export function createNote(docId: string, data: NoteCreateRequest) {
  return request<NoteResponse>(`/documents/${docId}/notes`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function updateNote(docId: string, noteId: string, data: NoteUpdateRequest) {
  return request<NoteResponse>(`/documents/${docId}/notes/${noteId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export function deleteNote(docId: string, noteId: string) {
  return request<void>(`/documents/${docId}/notes/${noteId}`, { method: 'DELETE' })
}

/** Глобальная заметка: document_id необязателен (заметка может быть без документа). */
export interface GlobalNoteCreateRequest {
  document_id?: string | null
  chunk_id?: string | null
  selected_text?: string | null
  text: string
  tag?: string | null
  page?: number | null
  /** [x, y] в PDF points, origin top-left (PyMuPDF). */
  position?: number[] | null
}

export interface GlobalNotesQuery {
  tag?: string
  document_id?: string
  /** YYYY-MM-DD */
  date_from?: string
  /** YYYY-MM-DD */
  date_to?: string
  sort?:
    | 'created_at_asc'
    | 'created_at_desc'
    | 'updated_at_asc'
    | 'updated_at_desc'
    | 'tag_asc'
    | 'document_id'
  limit?: number
  offset?: number
}

export function createGlobalNote(data: GlobalNoteCreateRequest) {
  return request<NoteResponse>('/notes', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

/** Глобальная память заметок: фильтрация/сортировка/пагинация на backend. */
export function listGlobalNotes(params: GlobalNotesQuery = {}) {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') qs.set(key, String(value))
  }
  const suffix = qs.size > 0 ? `?${qs.toString()}` : ''
  return request<NoteResponse[]>(`/notes${suffix}`)
}

export function updateGlobalNote(noteId: string, data: { text: string; tag?: string | null }) {
  return request<NoteResponse>(`/notes/${noteId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export function deleteGlobalNote(noteId: string) {
  return request<void>(`/notes/${noteId}`, { method: 'DELETE' })
}

function mockGraph(docId: string): KnowledgeGraphResponse {
  return {
    document_id: docId,
    entities: [],
    relations: [],
    stats: { mock: true },
  }
}

/** Knowledge graph: реальный эндпоинт, при ошибке — mock-заглушка. */
export async function getDocumentGraph(docId: string): Promise<KnowledgeGraphResponse> {
  try {
    return await request<KnowledgeGraphResponse>(`/documents/${docId}/knowledge-graph`)
  } catch {
    return mockGraph(docId)
  }
}

/** Формула документа (чанк knowledge layer) со статусом vision-распознавания. */
export interface DocumentFormulaItem {
  chunk_id: string
  page: number | null
  /** [x0, y0, x1, y1] в PDF points (1-based page); null, если региона нет. */
  bbox: number[] | null
  kind: string
  has_image: boolean
  latex: string | null
  status: 'ready' | 'failed' | 'not_generated'
}

export interface RecognizeFormulasResponse {
  ready: number
  failed: number
  skipped: number
  formulas: DocumentFormulaItem[]
}

export function getDocumentFormulas(docId: string) {
  return request<DocumentFormulaItem[]>(`/videos/documents/${docId}/formulas`)
}

/** URL PNG-картинки области формулы (для <img src>). */
export function getFormulaImageUrl(docId: string, chunkId: string) {
  return `${BASE_URL}/videos/documents/${docId}/formulas/${chunkId}/image`
}

/** On-demand распознавание LaTeX только для выбранных формул (1 AI-вызов на формулу). */
export function recognizeFormulas(docId: string, chunkIds: string[]) {
  return request<RecognizeFormulasResponse>(
    `/videos/documents/${docId}/formulas/recognize`,
    { method: 'POST', body: JSON.stringify({ chunk_ids: chunkIds }) },
  )
}

export async function processDocumentFile(
  file: File,
): Promise<ProcessMediaResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(
    `${BASE_URL}/videos/process-file`,
    {
      method: 'POST',
      body: formData,
    },
  )

  if (!response.ok) {
    const text = await response.text()
    throw new Error(
      text || `Document upload failed: ${response.status}`,
    )
  }

  return response.json()
}