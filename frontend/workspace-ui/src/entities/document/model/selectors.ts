import type { DocumentListItem, DocumentSnapshot } from '@/entities/document/model/types'

export function isDocumentReady(document: DocumentListItem | DocumentSnapshot): boolean {
  return document.status === 'completed'
}
