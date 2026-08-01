import { apiRequest } from '@/shared/api/client'

export interface TranslationSegmentDto {
  start: number
  end: number
  text: string
  enrichment?: {
    translation?: string | null
    translation_status?: 'ready' | 'failed' | 'not_generated'
  } | null
}

export interface TranslationPayloadDto {
  target_language?: string
  ai_profile_id?: string
  transcript_segments?: TranslationSegmentDto[]
}

export interface TranslationResponseDto {
  transcript_segments: TranslationSegmentDto[]
  translation_results: Record<string, TranslationPayloadDto>
}

export async function fetchTranslationSource(documentId: string): Promise<TranslationResponseDto> {
  return apiRequest<TranslationResponseDto>(`/videos/documents/${documentId}`)
}
