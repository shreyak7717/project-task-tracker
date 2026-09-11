import { Navigate, Route, Routes } from 'react-router-dom'

import { Layout } from '@/components/Layout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { AcceptInvitePage } from '@/features/auth/AcceptInvitePage'
import { LoginPage } from '@/features/auth/LoginPage'
import { AlertsPage } from '@/features/alerts/AlertsPage'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { ProjectDetailPage } from '@/features/projects/ProjectDetailPage'
import { ProjectsPage } from '@/features/projects/ProjectsPage'
import { TaskDetailPage } from '@/features/tasks/TaskDetailPage'
import { TaskListPage } from '@/features/tasks/TaskListPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/accept-invite" element={<AcceptInvitePage />} />

      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<DashboardPage />} />
        <Route path="/my-tasks" element={<TaskListPage mine />} />
        <Route path="/tasks" element={<TaskListPage />} />
        <Route path="/tasks/:taskId" element={<TaskDetailPage />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
