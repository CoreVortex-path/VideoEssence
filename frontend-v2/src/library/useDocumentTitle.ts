import { useQuery } from '@tanstack/react-query'
import { getDocumentSnapshot } from '../api/client'

/**
 * Лениво подтягивает отображаемое название документа из snapshot.
 * listDocuments() title не возвращает, а UUID пользователю не показываем.
 */
export function useDocumentTitle(documentId: string): string | null {
  const { data } = useQuery({
    queryKey: ['document-title', documentId],
    queryFn: () => getDocumentSnapshot(documentId),
    staleTime: Infinity,
  })
  return data?.title ?? null
}
