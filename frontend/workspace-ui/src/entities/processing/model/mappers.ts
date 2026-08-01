import type { ProcessingResponseDto } from '@/entities/processing/api/processing-api'
import type { ProcessingStatusData } from '@/entities/processing/model/types'

export function mapProcessingStatus(snapshot: ProcessingResponseDto): ProcessingStatusData {
  return {
    status: snapshot.status,
    progress: snapshot.progress,
    error: snapshot.error || null,
  }
}
