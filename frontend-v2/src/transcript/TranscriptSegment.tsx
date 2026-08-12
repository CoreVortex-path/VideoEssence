import { formatTime } from '../player/PlayerControls'

export interface TranscriptSegmentData {
  start: number
  end: number
  text: string
  translation?: string | null
}

interface TranscriptSegmentProps {
  segment: TranscriptSegmentData
  isActive: boolean
  onSeek: (time: number) => void
  onTranslate?: () => void
}

/** Один сегмент: timestamp, текст, inline-перевод по клику. */
export default function TranscriptSegment({
  segment,
  isActive,
  onSeek,
  onTranslate,
}: TranscriptSegmentProps) {
  return (
    <div
      data-active={isActive || undefined}
      onClick={onTranslate}
      className="transcript-segment group cursor-pointer px-3 py-2 transition-colors hover:bg-[rgba(20,184,166,0.05)]"
      style={
        isActive
          ? { borderLeft: '3px solid var(--accent)', paddingLeft: '9px' }
          : { borderLeft: '3px solid transparent', paddingLeft: '9px' }
      }
    >
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onSeek(segment.start)
          }}
          className="text-[11px] tabular-nums text-accent hover:text-accent-hover"
        >
          {formatTime(segment.start)}
        </button>
        <div className="flex-1" />
      </div>
      <p className="mt-0.5 text-[13px] leading-relaxed text-text-secondary">
        {segment.text}
      </p>
      {segment.translation && (
        <p className="mt-1 rounded border-l-2 border-accent bg-bg-card px-2 py-1 text-[12px] text-text-muted">
          {segment.translation}
        </p>
      )}
    </div>
  )
}