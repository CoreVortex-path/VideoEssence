import { useEffect } from 'react'
import { useAppStore } from '../store/appStore'

/**
 * Глобальные шорткаты (document listener, cleanup на размонтировании):
 * Z — zen mode, Space — play/pause, J/L — seek ±5с.
 * Игнорируются в полях ввода и contentEditable, а также с модификаторами.
 */
export function useGlobalShortcuts() {
  const toggleZenMode = useAppStore((s) => s.toggleZenMode)
  const togglePlay = useAppStore((s) => s.togglePlay)
  const seekBackward = useAppStore((s) => s.seekBackward)
  const seekForward = useAppStore((s) => s.seekForward)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null
      const tag = el?.tagName
      if (
        tag === 'INPUT' ||
        tag === 'TEXTAREA' ||
        tag === 'SELECT' ||
        el?.isContentEditable
      ) {
        return
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return

      const key = e.key.toLowerCase()
      if (key === 'z') toggleZenMode()
      else if (e.key === ' ') {
        e.preventDefault()
        togglePlay()
      } else if (key === 'j') seekBackward()
      else if (key === 'l') seekForward()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [toggleZenMode, togglePlay, seekBackward, seekForward])
}
