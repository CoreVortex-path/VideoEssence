import { useQuery } from '@tanstack/react-query'

import { fetchChapterSource } from '@/entities/chapter/api/chapter-api'
import { mapChapters } from '@/entities/chapter/model/mappers'
import type { ChapterItem } from '@/entities/chapter/model/types'
import { queryKeys } from '@/shared/api/query-keys'

export function useChapterQuery(documentId: string | null) {
  return useQuery<ChapterItem[]>({
    queryKey: queryKeys.documents.chapters(documentId),
    queryFn: async () => {
      if (!documentId) {
        throw new Error('documentId is required')
      }
      const snapshot = await fetchChapterSource(documentId)
      return mapChapters(snapshot.chapters || [])
    },
    enabled: Boolean(documentId),
  })
}
