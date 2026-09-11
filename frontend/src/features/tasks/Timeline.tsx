import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from 'sonner'

import { ErrorState, Loading } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { api, ApiError } from '@/lib/api'
import { STATUS_LABEL, relativeTime } from '@/lib/format'
import type { TaskEvent, TaskStatus } from '@/types'

function describe(e: TaskEvent): string {
  switch (e.event_type) {
    case 'created':
      return 'created this task'
    case 'field_changed':
      return `changed ${e.field} from "${e.old_value ?? '—'}" to "${e.new_value ?? '—'}"`
    case 'status_changed':
      return `moved status ${STATUS_LABEL[e.old_value as TaskStatus] ?? e.old_value} → ${
        STATUS_LABEL[e.new_value as TaskStatus] ?? e.new_value
      }`
    case 'assigned':
      return `assigned ${e.new_value}`
    case 'unassigned':
      return `unassigned ${e.old_value}`
    case 'dependency_added':
      return `added a dependency on "${e.new_value}"`
    case 'dependency_removed':
      return `removed the dependency on "${e.old_value}"`
    case 'commented':
      return 'commented'
    default:
      return e.event_type
  }
}

export function Timeline({ taskId }: { taskId: string }) {
  const qc = useQueryClient()
  const [body, setBody] = useState('')

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['timeline', taskId],
    queryFn: () => api<TaskEvent[]>(`/api/tasks/${taskId}/timeline`),
  })

  const comment = useMutation({
    mutationFn: () =>
      api(`/api/tasks/${taskId}/comments`, { method: 'POST', body: { body } }),
    onSuccess: () => {
      setBody('')
      qc.invalidateQueries({ queryKey: ['timeline', taskId] })
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : 'Failed to comment'),
  })

  return (
    <div className="rounded-lg border">
      <div className="max-h-[28rem] space-y-3 overflow-y-auto p-4">
        {isLoading && <Loading rows={4} />}
        {error && <ErrorState error={error} retry={() => void refetch()} />}
        {data?.map((e) => (
          <div key={e.id} className="text-sm">
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-medium">{e.actor?.full_name ?? 'System'}</span>
              <span className="shrink-0 text-xs text-muted-foreground">
                {relativeTime(e.created_at)}
              </span>
            </div>
            <div className="text-muted-foreground">{describe(e)}</div>
            {e.event_type === 'commented' && e.body && (
              <div className="mt-1 rounded-md bg-muted px-2 py-1.5 text-foreground">{e.body}</div>
            )}
          </div>
        ))}
      </div>
      <div className="border-t p-3">
        <Textarea
          placeholder="Add a comment…"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={2}
        />
        <Button
          size="sm"
          className="mt-2"
          disabled={!body.trim() || comment.isPending}
          onClick={() => comment.mutate()}
        >
          Comment
        </Button>
      </div>
    </div>
  )
}
