import { useQuery } from '@tanstack/react-query'

import { fetchDocumentList } from '@/entities/document/api/document-api'
import { mapDocumentListItem } from '@/entities/document/model/mappers'
import type { DocumentListItem } from '@/entities/document/model/types'
import { queryKeys } from '@/shared/api/query-keys'

export function useDocumentListQuery() {
  return useQuery<DocumentListItem[]>({
    queryKey: queryKeys.documents.list(),
    queryFn: async () => {
      const list = await fetchDocumentList()
      return list.map(mapDocumentListItem)
    },
  })
}
