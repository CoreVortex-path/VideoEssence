import { useQuery } from '@tanstack/react-query'

import { fetchProcessingSource, fetchTaskStatus } from '@/entities/processing/api/processing-api'
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

export interface TaskStatusData {
  taskId: string
  status: string
  progress: string
  error: string | null
  documentId: string | null
}

export function useTaskStatusQuery(taskId: string | null) {
  return useQuery<TaskStatusData>({
    queryKey: queryKeys.tasks.status(taskId),
    queryFn: async () => {
      if (!taskId) throw new Error('taskId is required')
      const dto = await fetchTaskStatus(taskId)
      return {
        taskId: dto.task_id,
        status: dto.status,
        progress: dto.progress,
        error: dto.error ?? null,
        documentId: dto.document_id ?? null,
      }
    },
    enabled: Boolean(taskId),
    // Stop polling once the task reaches a terminal state.
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'completed' || status === 'failed') return false
      return 3_000
    },
  })
}
