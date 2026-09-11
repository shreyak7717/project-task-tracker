import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { api, ApiError } from '@/lib/api'
import { ALL_STATUSES, STATUS_LABEL } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { BulkResult, ProjectMember } from '@/types'

type Change =
  | { kind: 'transition'; to_status: string }
  | { kind: 'set_assignees'; user_ids: string[] }
  | { kind: 'set_due_date'; due_date: string | null }

export function BulkBar({
  taskIds,
  projectId,
  onDone,
  onClear,
}: {
  taskIds: string[]
  projectId?: string
  onDone: () => void
  onClear: () => void
}) {
  const [mode, setMode] = useState<'status' | 'assignees' | 'due' | null>(null)
  const [result, setResult] = useState<BulkResult | null>(null)

  const apply = useMutation({
    mutationFn: (change: Change) =>
      api<BulkResult>('/api/tasks/bulk', {
        method: 'POST',
        body: { task_ids: taskIds, change },
      }),
    onSuccess: (r) => {
      // Show the full per-task report in a dialog; onDone() clears the
      // selection (and with it this bar), but `result` keeps this component
      // alive below so the dialog can still be seen and dismissed.
      setResult(r)
      setMode(null)
      toast[r.failed === 0 ? 'success' : 'warning'](
        `${r.succeeded} updated, ${r.failed} rejected`,
      )
      onDone()
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : 'Bulk action failed'),
  })

  if (taskIds.length === 0 && !result) return null

  return (
    <div
      className={cn(
        'mb-4 flex flex-wrap items-center gap-2 rounded-lg border bg-secondary/50 px-3 py-2 text-sm',
        taskIds.length === 0 && 'hidden',
      )}
    >
      <span className="font-medium">{taskIds.length} selected</span>
      <Button variant="outline" size="sm" onClick={() => setMode('status')}>
        Move status
      </Button>
      <Button variant="outline" size="sm" onClick={() => setMode('assignees')}>
        Set assignees
      </Button>
      <Button variant="outline" size="sm" onClick={() => setMode('due')}>
        Set due date
      </Button>
      <Button variant="ghost" size="sm" onClick={onClear} className="ml-auto">
        Clear
      </Button>

      <Dialog open={mode === 'status'} onOpenChange={(o) => !o && setMode(null)}>
        <DialogContent className="max-w-xs">
          <DialogHeader>
            <DialogTitle>Move to status</DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-2">
            {ALL_STATUSES.map((s) => (
              <Button
                key={s}
                variant="outline"
                size="sm"
                disabled={apply.isPending}
                onClick={() => apply.mutate({ kind: 'transition', to_status: s })}
              >
                {STATUS_LABEL[s]}
              </Button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            Illegal moves for individual tasks will be reported, not applied.
          </p>
        </DialogContent>
      </Dialog>

      <Dialog open={mode === 'assignees'} onOpenChange={(o) => !o && setMode(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Set assignees</DialogTitle>
          </DialogHeader>
          <AssigneePicker
            projectId={projectId}
            pending={apply.isPending}
            onApply={(user_ids) => apply.mutate({ kind: 'set_assignees', user_ids })}
          />
        </DialogContent>
      </Dialog>

      <Dialog open={mode === 'due'} onOpenChange={(o) => !o && setMode(null)}>
        <DialogContent className="max-w-xs">
          <DialogHeader>
            <DialogTitle>Set due date</DialogTitle>
          </DialogHeader>
          <DuePicker
            pending={apply.isPending}
            onApply={(due_date) => apply.mutate({ kind: 'set_due_date', due_date })}
          />
        </DialogContent>
      </Dialog>

      <Dialog open={!!result} onOpenChange={(o) => !o && setResult(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Result</DialogTitle>
          </DialogHeader>
          <p className="text-sm">
            {result?.succeeded} succeeded, {result?.failed} rejected.
          </p>
          {result && result.failed > 0 && (
            <ul className="max-h-60 space-y-1 overflow-y-auto text-sm">
              {result.results
                .filter((r) => !r.ok)
                .map((r) => (
                  <li key={r.task_id} className="text-destructive">
                    {r.error}
                  </li>
                ))}
            </ul>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

function AssigneePicker({
  projectId,
  pending,
  onApply,
}: {
  projectId?: string
  pending: boolean
  onApply: (ids: string[]) => void
}) {
  const [chosen, setChosen] = useState<Set<string>>(new Set())
  const { data: members } = useQuery({
    queryKey: ['project-members', projectId],
    queryFn: () => api<ProjectMember[]>(`/api/projects/${projectId}/members`),
    enabled: !!projectId,
  })

  if (!projectId) {
    return (
      <p className="text-sm text-muted-foreground">
        Filter by a project first — assignees are project-specific.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      <div className="max-h-52 space-y-1 overflow-y-auto">
        {members?.map((m) => (
          <label key={m.user.id} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={chosen.has(m.user.id)}
              onChange={(e) => {
                const next = new Set(chosen)
                if (e.target.checked) next.add(m.user.id)
                else next.delete(m.user.id)
                setChosen(next)
              }}
            />
            {m.user.full_name}
          </label>
        ))}
      </div>
      <Button
        size="sm"
        disabled={pending}
        onClick={() => onApply([...chosen])}
      >
        Apply to selected tasks
      </Button>
    </div>
  )
}

function DuePicker({
  pending,
  onApply,
}: {
  pending: boolean
  onApply: (date: string | null) => void
}) {
  const [date, setDate] = useState('')
  return (
    <div className="space-y-3">
      <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
      <div className="flex gap-2">
        <Button size="sm" disabled={pending || !date} onClick={() => onApply(date)}>
          Set
        </Button>
        <Button size="sm" variant="outline" disabled={pending} onClick={() => onApply(null)}>
          Clear due date
        </Button>
      </div>
    </div>
  )
}
