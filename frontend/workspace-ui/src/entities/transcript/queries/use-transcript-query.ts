import { useQuery } from '@tanstack/react-query'

import { fetchTranscriptSource } from '@/entities/transcript/api/transcript-api'
import { mapTranscriptSegments } from '@/entities/transcript/model/mappers'
import type { TranscriptSegment } from '@/entities/transcript/model/types'
import { queryKeys } from '@/shared/api/query-keys'

export function useTranscriptQuery(documentId: string | null) {
  return useQuery<TranscriptSegment[]>({
    queryKey: queryKeys.documents.transcript(documentId),
    queryFn: async () => {
      if (!documentId) {
        throw new Error('documentId is required')
      }
      const snapshot = await fetchTranscriptSource(documentId)
      return mapTranscriptSegments(snapshot.transcript_segments || [])
    },
    enabled: Boolean(documentId),
  })
}
