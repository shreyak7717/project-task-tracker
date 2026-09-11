import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { EmptyState, ErrorState, Loading, PageHeader } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api, ApiError } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { PRIORITY_LABEL, formatDate } from '@/lib/format'
import type { AlertsResponse } from '@/types'

export function AlertsPage() {
  const { user } = useAuth()
  const isManager = user?.role === 'manager'
  const qc = useQueryClient()
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['alerts'],
    queryFn: () => api<AlertsResponse>('/api/alerts'),
  })

  const dismiss = useMutation({
    mutationFn: (taskId: string) =>
      api(`/api/alerts/${taskId}/dismiss`, { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts'] })
      qc.invalidateQueries({ queryKey: ['alert-count'] })
    },
    onError: (e) =>
      toast.error(
        e instanceof ApiError ? e.message : 'Could not dismiss',
      ),
  })

  return (
    <div>
      <PageHeader
        title="Overdue alerts"
        description="Tasks past their due date that aren't done, in projects you can see"
      />
      {isLoading && <Loading />}
      {error && <ErrorState error={error} retry={() => void refetch()} />}
      {data && data.items.length === 0 && (
        <EmptyState message="Nothing overdue. Nice." />
      )}
      {data && data.items.length > 0 && (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Task</TableHead>
                <TableHead>Project</TableHead>
                <TableHead>Priority</TableHead>
                <TableHead>Due</TableHead>
                <TableHead>Overdue by</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((a) => (
                <TableRow key={a.id}>
                  <TableCell>
                    <Link to={`/tasks/${a.id}`} className="font-medium hover:underline">
                      {a.title}
                    </Link>
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {a.project_key}
                  </TableCell>
                  <TableCell>{PRIORITY_LABEL[a.priority]}</TableCell>
                  <TableCell className="text-muted-foreground">{formatDate(a.due_date)}</TableCell>
                  <TableCell className="text-red-600">
                    {a.days_overdue} day{a.days_overdue === 1 ? '' : 's'}
                  </TableCell>
                  <TableCell className="text-right">
                    {a.assigned_to_me ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={dismiss.isPending}
                        onClick={() => dismiss.mutate(a.id)}
                      >
                        Dismiss
                      </Button>
                    ) : (
                      <span className="text-xs text-muted-foreground">Not yours</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <p className="mt-3 text-xs text-muted-foreground">
        You can only dismiss alerts for tasks assigned to you. If a task's due date changes later,
        its alert comes back.
      </p>
    </div>
  )
}
