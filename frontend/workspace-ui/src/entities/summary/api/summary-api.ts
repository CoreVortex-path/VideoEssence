import { apiRequest } from '@/shared/api/client'

export interface SummaryResponseDto {
  summary?: string | null
}

export async function fetchSummarySource(documentId: string): Promise<SummaryResponseDto> {
  return apiRequest<SummaryResponseDto>(`/videos/documents/${documentId}`)
}
