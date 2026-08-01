import type { ReactNode } from 'react'

interface AppShellProps {
  header: ReactNode
  sidebar: ReactNode
  center: ReactNode
  rightPanel: ReactNode
  statusBar: ReactNode
}

export function AppShell({ header, sidebar, center, rightPanel, statusBar }: AppShellProps) {
  return (
    <div className="grid min-h-screen grid-rows-[auto_1fr_auto] bg-workspace-bg">
      {header}

      <div className="grid min-h-0 grid-cols-[280px_1fr_360px]">
        {sidebar}
        {center}
        {rightPanel}
      </div>

      {statusBar}
    </div>
  )
}
