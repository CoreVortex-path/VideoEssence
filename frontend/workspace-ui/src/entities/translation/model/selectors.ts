import type { TranslationSegment } from '@/entities/translation/model/types'

export function hasTranslationData(items: TranslationSegment[]): boolean {
  return items.some((item) => item.translatedText.trim().length > 0)
}
