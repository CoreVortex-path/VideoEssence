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

export interface TaskStatusDto {
  task_id: string
  status: string
  progress: string
  error?: string | null
  document_id?: string | null
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

export async function fetchTaskStatus(taskId: string): Promise<TaskStatusDto> {
  return apiRequest<TaskStatusDto>(`/videos/status/${taskId}`)
}

export async function processYouTubeUrl(
  url: string,
  modelSize = 'tiny',
  aiProfile = 'gemini_flash',
): Promise<UploadProcessingResponseDto> {
  return apiRequest<UploadProcessingResponseDto>('/videos/process-url', {
    method: 'POST',
    body: JSON.stringify({ url, model_size: modelSize, ai_profile: aiProfile }),
  })
}
