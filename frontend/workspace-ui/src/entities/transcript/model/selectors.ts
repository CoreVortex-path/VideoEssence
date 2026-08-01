import type { TranscriptSegment } from '@/entities/transcript/model/types'

interface SegmentSelectionOptions {
  hysteresisSeconds?: number
  previousSegmentId?: string | null
}

export function pickActiveSegment(
  segments: TranscriptSegment[],
  currentTime: number,
  previousSegmentId?: string | null,
  options?: SegmentSelectionOptions,
): TranscriptSegment | null {
  if (segments.length === 0) {
    return null
  }

  const hysteresisSeconds = options?.hysteresisSeconds ?? 0.75
  const previousSegment = previousSegmentId
    ? segments.find((segment) => segment.id === previousSegmentId) ?? null
    : null

  if (previousSegment) {
    const withinStickyWindow =
      currentTime >= previousSegment.start - hysteresisSeconds &&
      currentTime < previousSegment.end + hysteresisSeconds

    if (withinStickyWindow) {
      return previousSegment
    }
  }

  const exactMatch = segments.find((segment) => currentTime >= segment.start && currentTime < segment.end)
  if (exactMatch) {
    return exactMatch
  }

  const nearest = segments.reduce<TranscriptSegment | null>((best, segment) => {
    if (!best) {
      return segment
    }

    const bestDistance = Math.min(
      Math.abs(currentTime - best.start),
      Math.abs(currentTime - best.end),
    )
    const candidateDistance = Math.min(
      Math.abs(currentTime - segment.start),
      Math.abs(currentTime - segment.end),
    )

    return candidateDistance < bestDistance ? segment : best
  }, null)

  return nearest
}
