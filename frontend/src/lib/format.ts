import type { TaskPriority, TaskStatus } from '@/types'

export const STATUS_LABEL: Record<TaskStatus, string> = {
  backlog: 'Backlog',
  in_progress: 'In Progress',
  in_review: 'In Review',
  done: 'Done',
  blocked: 'Blocked',
}

export const STATUS_CLASS: Record<TaskStatus, string> = {
  backlog: 'bg-secondary text-secondary-foreground',
  in_progress: 'bg-blue-100 text-blue-800',
  in_review: 'bg-amber-100 text-amber-900',
  done: 'bg-emerald-100 text-emerald-800',
  blocked: 'bg-red-100 text-red-800',
}

export const PRIORITY_LABEL: Record<TaskPriority, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  urgent: 'Urgent',
}

export const PRIORITY_CLASS: Record<TaskPriority, string> = {
  low: 'text-muted-foreground',
  medium: 'text-foreground',
  high: 'text-amber-700 font-medium',
  urgent: 'text-red-700 font-semibold',
}

export const ALL_STATUSES: TaskStatus[] = [
  'backlog',
  'in_progress',
  'in_review',
  'done',
  'blocked',
]
export const ALL_PRIORITIES: TaskPriority[] = ['low', 'medium', 'high', 'urgent']

export function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.round(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 30) return `${days}d ago`
  return formatDate(iso)
}
