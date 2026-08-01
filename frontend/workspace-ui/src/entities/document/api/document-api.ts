import { apiRequest } from '@/shared/api/client'

const DEFAULT_BASE_URL = 'http://localhost:8000'

export interface DocumentListItemDto {
  document_id: string
  task_id: string
  status: string
  progress: string
  source_type: string
  language?: string | null
  transcript_language?: string | null
  ai_profile_id?: string | null
  ai_profile_name?: string | null
}

export interface DocumentSnapshotDto {
  task_id: string
  status: string
  progress: string
  summary?: string | null
  language?: string | null
  transcript_language?: string | null
  document_id?: string | null
}

export async function fetchDocumentList(): Promise<DocumentListItemDto[]> {
  return apiRequest<DocumentListItemDto[]>('/videos/documents')
}

export async function fetchDocumentSnapshot(documentId: string): Promise<DocumentSnapshotDto> {
  return apiRequest<DocumentSnapshotDto>(`/videos/documents/${documentId}`)
}

export function buildDocumentMediaUrl(documentId: string): string {
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? DEFAULT_BASE_URL
  return `${baseUrl}/videos/documents/${documentId}/media`
}
