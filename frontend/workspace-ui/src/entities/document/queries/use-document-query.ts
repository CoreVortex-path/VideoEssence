import { useQuery } from '@tanstack/react-query'

import { fetchDocumentSnapshot } from '@/entities/document/api/document-api'
import { mapDocumentSnapshot } from '@/entities/document/model/mappers'
import type { DocumentSnapshot } from '@/entities/document/model/types'
import { queryKeys } from '@/shared/api/query-keys'

export function useDocumentQuery(documentId: string | null) {
  return useQuery<DocumentSnapshot>({
    queryKey: queryKeys.documents.snapshot(documentId),
    queryFn: async () => {
      if (!documentId) {
        throw new Error('documentId is required')
      }
      const snapshot = await fetchDocumentSnapshot(documentId)
      return mapDocumentSnapshot(snapshot, documentId)
    },
    enabled: Boolean(documentId),
  })
}
