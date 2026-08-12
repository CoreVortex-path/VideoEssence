import { useCallback, useEffect, useRef, useState } from 'react'
import { useAppStore } from '../store/appStore'
import { useGlobalShortcuts } from '../hooks/useGlobalShortcuts'
import { useTaskPolling } from '../hooks/useTaskPolling'
import Sidebar from './Sidebar'
import RightPanel from './RightPanel'
import ResizeHandle from './ResizeHandle'
import ContentArea from './ContentArea'
import VideoPlayer from '../player/VideoPlayer'
import PlayerControls from '../player/PlayerControls'
import Waveform from '../player/Waveform'
import ChapterBar from '../player/ChapterBar'
import KnowledgeGraphView from '../graph/KnowledgeGraphView'
import CommandPalette from '../components/CommandPalette'
import ZenHint from '../components/ZenHint'

const RIGHT_MIN = 280
const RIGHT_MAX = 720
const RIGHT_DEFAULT = 340

export default function AppLayout() {
  const sidebarCollapsed = useAppStore((s) => s.sidebarCollapsed)
  const toggleSidebar = useAppStore((s) => s.toggleSidebar)
  const zenMode = useAppStore((s) => s.zenMode)
  const widthMode = useAppStore((s) => s.rightPanelWidthMode)
  const mainView = useAppStore((s) => s.mainView)
  const mediaUrl = useAppStore((s) => s.mediaUrl)

  useGlobalShortcuts()
  useTaskPolling()

  const [rightWidth, setRightWidth] = useState(RIGHT_DEFAULT)
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null)

  // Zen mode — класс на body
  useEffect(() => {
    document.body.classList.toggle('zen-mode', zenMode)
    return () => document.body.classList.remove('zen-mode')
  }, [zenMode])

  // Resize правой панели нативными mouse-событиями
  const startRightDrag = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      e.preventDefault()
      dragRef.current = { startX: e.clientX, startWidth: rightWidth }

      const onMove = (ev: MouseEvent) => {
        if (!dragRef.current) return
        const delta = dragRef.current.startX - ev.clientX
        const next = dragRef.current.startWidth + delta
        setRightWidth(Math.min(RIGHT_MAX, Math.max(RIGHT_MIN, next)))
      }
      const onUp = () => {
        dragRef.current = null
        window.removeEventListener('mousemove', onMove)
        window.removeEventListener('mouseup', onUp)
      }
      window.addEventListener('mousemove', onMove)
      window.addEventListener('mouseup', onUp)
    },
    [rightWidth],
  )

  const rightPanelWidth =
    widthMode === 'fullscreen' ? '100vw' : widthMode === 'wide' ? 560 : rightWidth

  return (
    <div
      className={`rp-${widthMode} flex h-screen w-screen overflow-hidden bg-bg-primary text-text-primary`}
    >
      {!zenMode && (
        <>
          <Sidebar collapsed={sidebarCollapsed} onToggle={toggleSidebar} />
          <ResizeHandle
            onMouseDown={() => toggleSidebar()}
            title="Свернуть / развернуть сайдбар"
          />
        </>
      )}

      <main className="flex min-w-0 flex-1 flex-col">
        {mainView === 'graph' ? (
          <KnowledgeGraphView />
        ) : (
          <>
            {/* Player area — фиксирована сверху, никакого mini-player */}
            <VideoPlayer />
            {mediaUrl && !zenMode && (
              <>
                <Waveform />
                <ChapterBar />
                <PlayerControls />
              </>
            )}

            {/* Tabs: Transcript | Summary | Translation */}
            <ContentArea />
          </>
        )}
      </main>

      {!zenMode && (
        <>
          <ResizeHandle onMouseDown={startRightDrag} title="Изменить ширину панели" />
          <RightPanel width={rightPanelWidth} />
        </>
      )}

      <CommandPalette />
      <ZenHint />
    </div>
  )
}
