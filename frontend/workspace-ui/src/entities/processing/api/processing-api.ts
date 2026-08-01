import { apiRequest } from '@/shared/api/client'

export interface ProcessingResponseDto {
  status: string
  progress: string
  error?: string | null
}

export interface UploadProcessingResponseDto {
  task_id: string
  status: string
  progress: string
  source_type: string
}

export async function fetchProcessingSource(documentId: string): Promise<ProcessingResponseDto> {
  return apiRequest<ProcessingResponseDto>(`/videos/documents/${documentId}`)
}

export async function uploadProcessingDocument(formData: FormData): Promise<UploadProcessingResponseDto> {
  return apiRequest<UploadProcessingResponseDto>('/videos/process-file', {
    method: 'POST',
    body: formData,
  })
}
