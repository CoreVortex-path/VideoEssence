import { useQuery } from '@tanstack/react-query'

import { fetchProcessingSource } from '@/entities/processing/api/processing-api'
import { mapProcessingStatus } from '@/entities/processing/model/mappers'
import type { ProcessingStatusData } from '@/entities/processing/model/types'
import { queryKeys } from '@/shared/api/query-keys'

export function useProcessingStatusQuery(documentId: string | null) {
  return useQuery<ProcessingStatusData>({
    queryKey: queryKeys.documents.processing(documentId),
    queryFn: async () => {
      if (!documentId) {
        throw new Error('documentId is required')
      }
      const snapshot = await fetchProcessingSource(documentId)
      return mapProcessingStatus(snapshot)
    },
    enabled: Boolean(documentId),
    refetchInterval: 5_000,
  })
}
