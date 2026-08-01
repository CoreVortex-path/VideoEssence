import {
  buildDocumentMediaUrl,
  type DocumentListItemDto,
  type DocumentSnapshotDto,
} from '@/entities/document/api/document-api'
import type { DocumentListItem, DocumentSnapshot } from '@/entities/document/model/types'

function normalizeStatus(value: string): DocumentListItem['status'] {
  if (value === 'processing' || value === 'completed' || value === 'failed') {
    return value
  }
  return 'created'
}

export function mapDocumentListItem(dto: DocumentListItemDto): DocumentListItem {
  return {
    id: dto.document_id,
    taskId: dto.task_id,
    // TODO(frontend-phase2): replace with real document title once backend exposes it.
    title: dto.document_id,
    language: dto.language || dto.transcript_language || 'unknown',
    status: normalizeStatus(dto.status),
    progress: dto.progress,
  }
}

export function mapDocumentSnapshot(dto: DocumentSnapshotDto, documentId: string): DocumentSnapshot {
  return {
    id: dto.document_id || documentId,
    taskId: dto.task_id,
    status: normalizeStatus(dto.status),
    progress: dto.progress,
    summary: dto.summary || '',
    transcriptLanguage: dto.transcript_language || dto.language || 'unknown',
    mediaUrl: dto.document_id ? buildDocumentMediaUrl(dto.document_id) : null,
  }
}
