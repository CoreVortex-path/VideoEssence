import type { TranscriptSegmentDto } from '@/entities/transcript/api/transcript-api'
import type { TranscriptSegment } from '@/entities/transcript/model/types'
import { formatSeconds } from '@/shared/utils/time'

export function mapTranscriptSegments(items: TranscriptSegmentDto[]): TranscriptSegment[] {
  return items.map((item, index) => ({
    id: `chunk-${index}`,
    start: item.start,
    end: item.end,
    timestampLabel: formatSeconds(item.start),
    text: item.text,
  }))
}
