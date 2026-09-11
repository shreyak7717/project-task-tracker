import { AlertCircle, Inbox } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiError } from '@/lib/api'
import { avatarColor, initials, STATUS_CLASS, STATUS_LABEL } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { TaskStatus } from '@/types'

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>}
      </div>
      {action}
    </div>
  )
}

export function AvatarStack({
  people,
  max = 4,
}: {
  people: { id: string; full_name: string }[]
  max?: number
}) {
  if (people.length === 0) return <span className="text-muted-foreground">—</span>
  const shown = people.slice(0, max)
  const overflow = people.length - shown.length
  return (
    <div className="flex -space-x-2">
      {shown.map((p) => (
        <span
          key={p.id}
          title={p.full_name}
          className={cn(
            'grid size-6 shrink-0 place-items-center rounded-full border-2 border-background text-[10px] font-bold',
            avatarColor(p.full_name),
          )}
        >
          {initials(p.full_name)}
        </span>
      ))}
      {overflow > 0 && (
        <span
          title={people
            .slice(max)
            .map((p) => p.full_name)
            .join(', ')}
          className="grid size-6 shrink-0 place-items-center rounded-full border-2 border-background bg-muted text-[10px] font-medium text-muted-foreground"
        >
          +{overflow}
        </span>
      )}
    </div>
  )
}

export function StatusBadge({ status }: { status: TaskStatus }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium',
        STATUS_CLASS[status],
      )}
    >
      {STATUS_LABEL[status]}
    </span>
  )
}

export function Loading({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  )
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const message =
    error instanceof ApiError || error instanceof Error ? error.message : 'Something went wrong'
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed p-8 text-center">
      <AlertCircle className="size-6 text-destructive" />
      <p className="text-sm text-muted-foreground">{message}</p>
      {retry && (
        <Button variant="outline" size="sm" onClick={retry}>
          Try again
        </Button>
      )}
    </div>
  )
}

export function EmptyState({ message, action }: { message: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed p-10 text-center">
      <Inbox className="size-6 text-muted-foreground" />
      <p className="text-sm text-muted-foreground">{message}</p>
      {action}
    </div>
  )
}
