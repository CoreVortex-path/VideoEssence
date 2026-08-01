import { useQuery } from '@tanstack/react-query'

import { fetchSummarySource } from '@/entities/summary/api/summary-api'
import { mapSummary } from '@/entities/summary/model/mappers'
import type { SummaryData } from '@/entities/summary/model/types'
import { queryKeys } from '@/shared/api/query-keys'

export function useSummaryQuery(documentId: string | null) {
  return useQuery<SummaryData>({
    queryKey: queryKeys.documents.summary(documentId),
    queryFn: async () => {
      if (!documentId) {
        throw new Error('documentId is required')
      }
      const snapshot = await fetchSummarySource(documentId)
      return mapSummary(snapshot)
    },
    enabled: Boolean(documentId),
  })
}
