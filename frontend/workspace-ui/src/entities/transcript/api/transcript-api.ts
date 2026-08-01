import { apiRequest } from '@/shared/api/client'

export interface TranscriptSegmentDto {
  start: number
  end: number
  text: string
}

export interface TranscriptResponseDto {
  transcript_segments: TranscriptSegmentDto[]
}

export async function fetchTranscriptSource(documentId: string): Promise<TranscriptResponseDto> {
  return apiRequest<TranscriptResponseDto>(`/videos/documents/${documentId}`)
}
