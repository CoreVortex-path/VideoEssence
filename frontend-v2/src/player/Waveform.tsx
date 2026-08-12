import { useEffect, useMemo, useRef, useState } from 'react'
import { useAppStore } from '../store/appStore'
import type { WavePeak } from '../store/appStore'

const HIGH_RES = 4096

export default function Waveform() {
  const containerRef = useRef<HTMLDivElement>(null)

  const mediaUrl = useAppStore((s) => s.mediaUrl)
  const sourceType = useAppStore((s) => s.sourceType)
  const playerTime = useAppStore((s) => s.playerTime)
  const duration = useAppStore((s) => s.duration)
  const waveformPeaks = useAppStore((s) => s.waveformPeaks)
  const setWaveformPeaks = useAppStore((s) => s.setWaveformPeaks)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const [barCount, setBarCount] = useState(300)

  useEffect(() => {
    const update = () => {
      const width = containerRef.current?.clientWidth ?? window.innerWidth
      setBarCount(Math.max(120, Math.floor(width / 4)))
    }

    update()

    const ro =
      typeof ResizeObserver !== 'undefined'
        ? new ResizeObserver((entries) => {
            const width = entries[0]?.contentRect.width ?? window.innerWidth
            setBarCount(Math.max(120, Math.floor(width / 4)))
          })
        : null

    if (ro && containerRef.current) ro.observe(containerRef.current)

    window.addEventListener('resize', update)

    return () => {
      ro?.disconnect()
      window.removeEventListener('resize', update)
    }
  }, [])

  useEffect(() => {
    if (sourceType === 'youtube' || !mediaUrl || waveformPeaks) return

    let cancelled = false

    setLoading(true)
    setError(false)

    const ctx = new AudioContext()

    fetch(mediaUrl)
      .then((r) => {
        if (!r.ok) throw new Error()
        return r.arrayBuffer()
      })
      .then((buf) => ctx.decodeAudioData(buf))
      .then((audio) => {
        if (cancelled) return

        const left = audio.getChannelData(0)
        const right =
          audio.numberOfChannels > 1
            ? audio.getChannelData(1)
            : left

        const samples = left.length
        const block = Math.max(1, Math.floor(samples / HIGH_RES))

        const peaks: WavePeak[] = []

        let globalPeak = 0

        for (let i = 0; i < HIGH_RES; i++) {
          const start = i * block
          const end = Math.min(start + block, samples)

          let min = 1
          let max = -1

          for (let j = start; j < end; j++) {
            const sample = (left[j] + right[j]) * 0.5

            if (sample > max) max = sample
            if (sample < min) min = sample
          }

          globalPeak = Math.max(
            globalPeak,
            Math.abs(min),
            Math.abs(max)
          )

          peaks.push({ min, max })
        }

        const normalized = peaks.map((p) => ({
          min: p.min / globalPeak,
          max: p.max / globalPeak,
        }))

        setWaveformPeaks(normalized)
        setLoading(false)
      })
      .catch(() => {
        if (!cancelled) {
          setError(true)
          setLoading(false)
        }
      })
      .finally(() => {
        if (ctx.state !== 'closed') ctx.close()
      })

    return () => {
      cancelled = true
      if (ctx.state !== 'closed') ctx.close()
    }
  }, [mediaUrl, waveformPeaks, setWaveformPeaks, sourceType])

  const displayPeaks = useMemo(() => {
    if (!waveformPeaks) return null

    const ratio = waveformPeaks.length / barCount
    const result: WavePeak[] = []

    for (let i = 0; i < barCount; i++) {
      const start = Math.floor(i * ratio)
      const end = Math.max(start + 1, Math.floor((i + 1) * ratio))

      let min = 1
      let max = -1

      for (let j = start; j < end; j++) {
        const p = waveformPeaks[j]
        if (!p) continue

        if (p.min < min) min = p.min
        if (p.max > max) max = p.max
      }

      result.push({ min, max })
    }

    return result
  }, [waveformPeaks, barCount])

  const progress =
    duration > 0 ? (playerTime / duration) * 100 : 0

  const isYouTube = sourceType === 'youtube' || !mediaUrl

  if (isYouTube) {
    return (
      <div className="flex h-[32px] items-center px-4">
        <div className="h-[2px] w-full rounded-full bg-border overflow-hidden">
          <div
            className="h-full bg-accent transition-all duration-200"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div
        ref={containerRef}
        className="flex h-[32px] items-center justify-center px-4"
      >
        <div className="h-[2px] w-full rounded-full bg-border overflow-hidden">
          <div
            className="h-full animate-pulse bg-accent/40"
            style={{ width: '40%' }}
          />
        </div>
      </div>
    )
  }

  if (error || !displayPeaks) {
    return (
      <div
        ref={containerRef}
        className="flex h-[32px] items-center px-4"
      >
        <div className="h-[2px] w-full rounded-full bg-border overflow-hidden">
          <div
            className="h-full bg-accent"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    )
  }

  const activeBars =
    duration > 0
      ? Math.floor((playerTime / duration) * barCount)
      : 0

  const transform = (v: number) =>
    Math.pow(Math.abs(v), 0.82)

  return (
    <div
      ref={containerRef}
      className="relative flex h-[32px] items-center overflow-hidden px-4"
      aria-hidden="true"
    >
      {displayPeaks.map((p, i) => {
        const active = i < activeBars

        const top = Math.max(2, transform(p.max) * 48)
        const bottom = Math.max(2, transform(-p.min) * 48)

        return (
          <div
            key={i}
            className="relative shrink-0"
            style={{
              width: '3px',
              marginRight: '1px',
              height: '100%',
            }}
          >
            <div
              className="absolute left-0 w-full rounded-full"
              style={{
                bottom: '50%',
                height: `${top}%`,
                background: active
                  ? 'var(--accent)'
                  : 'var(--border)',
              }}
            />

            <div
              className="absolute left-0 w-full rounded-full"
              style={{
                top: '50%',
                height: `${bottom}%`,
                background: active
                  ? 'var(--accent)'
                  : 'var(--border)',
              }}
            />
          </div>
        )
      })}
    </div>
  )
}