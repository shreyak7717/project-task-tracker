import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Trash2, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { ErrorState, Loading, StatusBadge } from '@/components/common'
import { Timeline } from '@/features/tasks/Timeline'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { api, ApiError } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { ALL_PRIORITIES, PRIORITY_LABEL, STATUS_LABEL } from '@/lib/format'
import type { ProjectMember, Task, TaskDetail } from '@/types'

export function TaskDetailPage() {
  const { taskId } = useParams()
  const { user } = useAuth()
  const isManager = user?.role === 'manager'
  const qc = useQueryClient()
  const navigate = useNavigate()

  const key = ['task', taskId]
  const { data: task, isLoading, error, refetch } = useQuery({
    queryKey: key,
    queryFn: () => api<TaskDetail>(`/api/tasks/${taskId}`),
  })

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: key })
    qc.invalidateQueries({ queryKey: ['timeline', taskId] })
    qc.invalidateQueries({ queryKey: ['tasks'] })
  }
  const onError = (e: unknown) =>
    toast.error(e instanceof ApiError ? e.message : 'Something went wrong')

  const patch = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<TaskDetail>(`/api/tasks/${taskId}`, { method: 'PATCH', body }),
    onSuccess: () => {
      toast.success('Task updated')
      invalidate()
    },
    onError,
  })
  const transition = useMutation({
    mutationFn: (to_status: string) =>
      api(`/api/tasks/${taskId}/transition`, { method: 'POST', body: { to_status } }),
    onSuccess: () => {
      toast.success('Status updated')
      invalidate()
    },
    onError,
  })
  const removeTask = useMutation({
    mutationFn: () => api(`/api/tasks/${taskId}`, { method: 'DELETE' }),
    onSuccess: () => {
      toast.success('Task deleted')
      navigate(-1)
    },
    onError,
  })
  const setAssignees = useMutation({
    mutationFn: (user_ids: string[]) =>
      api(`/api/tasks/${taskId}/assignees`, { method: 'PUT', body: { user_ids } }),
    onSuccess: () => {
      toast.success('Assignees updated')
      invalidate()
    },
    onError,
  })
  const addDep = useMutation({
    mutationFn: (depends_on_task_id: string) =>
      api(`/api/tasks/${taskId}/dependencies`, {
        method: 'POST',
        body: { depends_on_task_id },
      }),
    onSuccess: () => {
      toast.success('Dependency added')
      invalidate()
    },
    onError,
  })
  const removeDep = useMutation({
    mutationFn: (depId: string) =>
      api(`/api/tasks/${taskId}/dependencies/${depId}`, { method: 'DELETE' }),
    onSuccess: () => {
      toast.success('Dependency removed')
      invalidate()
    },
    onError,
  })

  if (isLoading) return <Loading rows={8} />
  if (error || !task) return <ErrorState error={error} retry={() => void refetch()} />

  return (
    <div>
      <button
        onClick={() => navigate(-1)}
        className="mb-4 flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Back
      </button>

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-6">
          <EditableFields task={task} onSave={(b) => patch.mutate(b)} pending={patch.isPending} />

          <section>
            <h3 className="mb-2 text-sm font-medium">Status</h3>
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={task.status} />
              {task.blocked_by_unfinished_dependency && (
                <span className="text-xs text-amber-700">waiting on unfinished blockers</span>
              )}
              <span className="mx-1 text-muted-foreground">→</span>
              {task.allowed_transitions.length === 0 && (
                <span className="text-xs text-muted-foreground">no moves available</span>
              )}
              {task.allowed_transitions.map((s) => (
                <Button
                  key={s}
                  size="sm"
                  variant="outline"
                  disabled={transition.isPending}
                  onClick={() => transition.mutate(s)}
                >
                  {task.status === 'blocked' ? `Unblock → ${STATUS_LABEL[s]}` : STATUS_LABEL[s]}
                </Button>
              ))}
            </div>
          </section>

          <AssigneesPanel
            task={task}
            onChange={(ids) => setAssignees.mutate(ids)}
            pending={setAssignees.isPending}
          />

          <DependenciesPanel
            task={task}
            onAdd={(id) => addDep.mutate(id)}
            onRemove={(id) => removeDep.mutate(id)}
            pending={addDep.isPending || removeDep.isPending}
          />

          {isManager && (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => {
                if (confirm('Delete this task? This cannot be undone.')) removeTask.mutate()
              }}
            >
              <Trash2 className="size-4" /> Delete task
            </Button>
          )}
        </div>

        <div>
          <h3 className="mb-2 text-sm font-medium">History</h3>
          <Timeline taskId={task.id} />
        </div>
      </div>
    </div>
  )
}

function EditableFields({
  task,
  onSave,
  pending,
}: {
  task: TaskDetail
  onSave: (body: Record<string, unknown>) => void
  pending: boolean
}) {
  const [title, setTitle] = useState(task.title)
  const [description, setDescription] = useState(task.description)
  const [priority, setPriority] = useState(task.priority)
  const [due, setDue] = useState(task.due_date ?? '')

  useEffect(() => {
    setTitle(task.title)
    setDescription(task.description)
    setPriority(task.priority)
    setDue(task.due_date ?? '')
  }, [task])

  const dirty =
    title !== task.title ||
    description !== task.description ||
    priority !== task.priority ||
    due !== (task.due_date ?? '')

  return (
    <div className="space-y-3">
      <Input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        className="text-base font-semibold"
      />
      <Textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="No description"
        rows={4}
      />
      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-1">
          <Label className="text-xs">Priority</Label>
          <Select value={priority} onValueChange={(v) => setPriority(v as typeof priority)}>
            <SelectTrigger className="w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ALL_PRIORITIES.map((p) => (
                <SelectItem key={p} value={p}>
                  {PRIORITY_LABEL[p]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Due date</Label>
          <Input
            type="date"
            value={due}
            onChange={(e) => setDue(e.target.value)}
            className="w-40"
          />
        </div>
        {dirty && (
          <Button
            size="sm"
            disabled={pending}
            onClick={() =>
              onSave({
                title,
                description,
                priority,
                due_date: due === '' ? null : due,
              })
            }
          >
            Save changes
          </Button>
        )}
      </div>
    </div>
  )
}

function AssigneesPanel({
  task,
  onChange,
  pending,
}: {
  task: TaskDetail
  onChange: (ids: string[]) => void
  pending: boolean
}) {
  const { data: members } = useQuery({
    queryKey: ['project-members', task.project_id],
    queryFn: () => api<ProjectMember[]>(`/api/projects/${task.project_id}/members`),
  })
  const current = new Set(task.assignees.map((a) => a.id))

  return (
    <section>
      <h3 className="mb-2 text-sm font-medium">Assignees</h3>
      <div className="mb-2 flex flex-wrap gap-1.5">
        {task.assignees.length === 0 && (
          <span className="text-xs text-muted-foreground">Nobody assigned</span>
        )}
        {task.assignees.map((a) => (
          <Badge key={a.id} variant="secondary">
            {a.full_name}
            <button
              className="ml-1"
              disabled={pending}
              onClick={() => onChange(task.assignees.filter((x) => x.id !== a.id).map((x) => x.id))}
            >
              <X className="size-3" />
            </button>
          </Badge>
        ))}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {members
          ?.filter((m) => !current.has(m.user.id))
          .map((m) => (
            <Button
              key={m.user.id}
              size="sm"
              variant="outline"
              disabled={pending}
              onClick={() => onChange([...current, m.user.id])}
            >
              + {m.user.full_name}
            </Button>
          ))}
      </div>
    </section>
  )
}

function DependenciesPanel({
  task,
  onAdd,
  onRemove,
  pending,
}: {
  task: TaskDetail
  onAdd: (id: string) => void
  onRemove: (id: string) => void
  pending: boolean
}) {
  const { data } = useQuery({
    queryKey: ['project-tasks', task.project_id],
    queryFn: () => api<Task[]>(`/api/projects/${task.project_id}/tasks`),
  })
  const depIds = new Set(task.dependencies.map((d) => d.id))
  const candidates = (data ?? []).filter((t) => t.id !== task.id && !depIds.has(t.id))
  const [pick, setPick] = useState('')

  return (
    <section>
      <h3 className="mb-2 text-sm font-medium">Blocked by</h3>
      <ul className="mb-2 space-y-1">
        {task.dependencies.length === 0 && (
          <li className="text-xs text-muted-foreground">No blocking tasks</li>
        )}
        {task.dependencies.map((d) => (
          <li key={d.id} className="flex items-center gap-2 text-sm">
            <Link to={`/tasks/${d.id}`} className="hover:underline">
              {d.title}
            </Link>
            <StatusBadge status={d.status} />
            <button
              className="text-muted-foreground hover:text-destructive"
              disabled={pending}
              onClick={() => onRemove(d.id)}
            >
              <X className="size-3.5" />
            </button>
          </li>
        ))}
      </ul>
      <div className="flex gap-2">
        <Select value={pick} onValueChange={setPick}>
          <SelectTrigger className="w-64">
            <SelectValue placeholder="Add a blocking task" />
          </SelectTrigger>
          <SelectContent>
            {candidates.map((t) => (
              <SelectItem key={t.id} value={t.id}>
                {t.title}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          size="sm"
          variant="outline"
          disabled={!pick || pending}
          onClick={() => {
            onAdd(pick)
            setPick('')
          }}
        >
          Add
        </Button>
      </div>
    </section>
  )
}
