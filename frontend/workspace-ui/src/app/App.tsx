import { Route, Routes } from 'react-router-dom'

import { WorkspacePage } from '@/pages/workspace-page/ui/WorkspacePage'

export function App() {
  return (
    <Routes>
      <Route path="/" element={<WorkspacePage />} />
    </Routes>
  )
}
