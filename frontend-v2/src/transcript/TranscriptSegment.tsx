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

/** Один сегмент: строка «таймкод слева, текст справа», inline-перевод по клику. */
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
      className={`transcript-segment group flex cursor-pointer items-start gap-3 px-3 py-2.5 transition-colors hover:bg-accent/5 ${
        isActive ? 'bg-accent/5' : ''
      }`}
      style={
        isActive
          ? { borderLeft: '3px solid var(--accent)', paddingLeft: '9px' }
          : { borderLeft: '3px solid transparent', paddingLeft: '9px' }
      }
    >
      <div className="w-12 shrink-0 pt-0.5">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onSeek(segment.start)
          }}
          className="text-[13px] tabular-nums text-accent hover:text-accent-hover"
        >
          {formatTime(segment.start)}
        </button>
      </div>
      <div className="min-w-0 flex-1">
        {/* data-segment-start: привязка выделения текста к таймкоду сегмента */}
        <p
          data-segment-start={segment.start}
          className="text-[14px] leading-relaxed text-text-primary"
        >
          {segment.text}
        </p>
        {segment.translation && (
          <p className="mt-1.5 rounded-r border-l-[3px] border-accent/40 bg-bg-card py-1.5 pl-3 pr-2 text-[13px] leading-relaxed text-text-secondary">
            <span className="mr-1.5 text-[11px] font-medium uppercase text-accent">RU</span>
            {segment.translation}
          </p>
        )}
      </div>
      {!segment.translation && (
        <span
          aria-hidden
          className="shrink-0 pt-1 text-[12px] leading-none text-text-dim opacity-0 transition-opacity group-hover:opacity-100 group-hover:text-accent"
        >
          文
        </span>
      )}
    </div>
  )
}
