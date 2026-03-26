import { Navigate, Route, Routes } from 'react-router-dom'
import { Sidebar } from './components/Sidebar'
import { RemindersPage } from './pages/RemindersPage'
import { SettingsPage } from './pages/SettingsPage'
import { TasksPage } from './pages/TasksPage'
import { TimerPage } from './pages/TimerPage'
import { VoiceIndicator } from './components/VoiceIndicator'
import { NotificationCenter } from './components/NotificationCenter'
import { DesktopTopBar } from './components/DesktopTopBar'

export default function App() {
  return (
    <div className="relative min-h-screen" style={{ background: 'var(--bg-base)', color: 'var(--text-primary)' }}>
      <div className="relative flex min-h-screen w-full flex-col">
        <DesktopTopBar />
        <div className="flex min-h-0 flex-1 flex-col md:flex-row md:gap-4 md:px-4 md:py-4">
          <Sidebar />
          <main className="flex-1 px-4 py-4 md:px-6 md:py-6">
            <Routes>
              <Route path="/" element={<Navigate to="/tasks" replace />} />
              <Route path="/tasks" element={<TasksPage />} />
              <Route path="/timer" element={<TimerPage />} />
              <Route path="/reminders" element={<RemindersPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Routes>
          </main>
        </div>
      </div>
      <VoiceIndicator />
      <NotificationCenter />
    </div>
  )
}
