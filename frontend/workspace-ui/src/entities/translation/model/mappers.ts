import type {
  TranslationResponseDto,
  TranslationSegmentDto,
} from '@/entities/translation/api/translation-api'
import type { TranslationSegment } from '@/entities/translation/model/types'

function firstTranslationPayload(snapshot: TranslationResponseDto) {
  const values = Object.values(snapshot.translation_results || {})
  return values[0]
}

function mapSegment(item: TranslationSegmentDto, index: number): TranslationSegment {
  return {
    id: `trs-${index}`,
    start: item.start,
    end: item.end,
    sourceText: item.text,
    translatedText: item.enrichment?.translation || '',
  }
}

export function mapTranslationSegments(snapshot: TranslationResponseDto): TranslationSegment[] {
  const payload = firstTranslationPayload(snapshot)
  const translated = payload?.transcript_segments
  if (Array.isArray(translated) && translated.length > 0) {
    return translated.map(mapSegment)
  }

  return (snapshot.transcript_segments || []).map(mapSegment)
}
