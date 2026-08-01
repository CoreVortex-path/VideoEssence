import { useQuery } from '@tanstack/react-query'

import { fetchTranslationSource } from '@/entities/translation/api/translation-api'
import { mapTranslationSegments } from '@/entities/translation/model/mappers'
import type { TranslationSegment } from '@/entities/translation/model/types'
import { queryKeys } from '@/shared/api/query-keys'

export function useTranslationQuery(documentId: string | null) {
  return useQuery<TranslationSegment[]>({
    queryKey: queryKeys.documents.translation(documentId),
    queryFn: async () => {
      if (!documentId) {
        throw new Error('documentId is required')
      }
      const snapshot = await fetchTranslationSource(documentId)
      return mapTranslationSegments(snapshot)
    },
    enabled: Boolean(documentId),
  })
}
