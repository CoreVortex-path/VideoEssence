import { apiRequest } from '@/shared/api/client'

export interface ChapterDto {
  title: string
  summary: string
  start: number
}

export interface ChapterResponseDto {
  chapters: ChapterDto[]
}

export async function fetchChapterSource(documentId: string): Promise<ChapterResponseDto> {
  return apiRequest<ChapterResponseDto>(`/videos/documents/${documentId}`)
}
