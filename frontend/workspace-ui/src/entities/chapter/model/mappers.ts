import type { ChapterDto } from '@/entities/chapter/api/chapter-api'
import type { ChapterItem } from '@/entities/chapter/model/types'

export function mapChapters(items: ChapterDto[]): ChapterItem[] {
  return items.map((item, index) => ({
    id: `chapter-${index}`,
    title: item.title,
    summary: item.summary,
    start: item.start,
  }))
}
