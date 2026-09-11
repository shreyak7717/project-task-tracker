import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, X } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { EmptyState, ErrorState, Loading, PageHeader, StatusBadge } from '@/components/common'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { api, ApiError } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { PRIORITY_LABEL, formatDate } from '@/lib/format'
import type { Project, ProjectMember, Task, User } from '@/types'

export function ProjectDetailPage() {
  const { projectId } = useParams()
  const { user } = useAuth()
  const isManager = user?.role === 'manager'

  const { data: project, isLoading, error, refetch } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api<Project>(`/api/projects/${projectId}`),
  })

  if (isLoading) return <Loading rows={8} />
  if (error || !project) return <ErrorState error={error} retry={() => void refetch()} />

  return (
    <div>
      <Link
        to="/projects"
        className="mb-4 flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Projects
      </Link>
      <PageHeader
        title={project.name}
        description={`${project.key} · owner ${project.owner.full_name}`}
        action={project.is_archived ? <Badge variant="secondary">Archived</Badge> : undefined}
      />

      <Tabs defaultValue="tasks">
        <TabsList>
          <TabsTrigger value="tasks">Tasks</TabsTrigger>
          <TabsTrigger value="members">Members</TabsTrigger>
          {isManager && <TabsTrigger value="settings">Settings</TabsTrigger>}
        </TabsList>

        <TabsContent value="tasks">
          <TasksTab projectId={project.id} />
        </TabsContent>
        <TabsContent value="members">
          <MembersTab projectId={project.id} ownerId={project.owner_id} canEdit={isManager} />
        </TabsContent>
        {isManager && (
          <TabsContent value="settings">
            <SettingsTab project={project} />
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}

function TasksTab({ projectId }: { projectId: string }) {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [priority, setPriority] = useState('medium')

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['project-tasks', projectId],
    queryFn: () => api<Task[]>(`/api/projects/${projectId}/tasks`),
  })

  const create = useMutation({
    mutationFn: () =>
      api(`/api/projects/${projectId}/tasks`, {
        method: 'POST',
        body: { title, description: '', priority },
      }),
    onSuccess: () => {
      toast.success('Task created')
      qc.invalidateQueries({ queryKey: ['project-tasks', projectId] })
      setOpen(false)
      setTitle('')
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : 'Failed'),
  })

  return (
    <div>
      <div className="mb-3 flex justify-end">
        <Button size="sm" onClick={() => setOpen(true)}>
          New task
        </Button>
      </div>
      {isLoading && <Loading />}
      {error && <ErrorState error={error} retry={() => void refetch()} />}
      {data && data.length === 0 && <EmptyState message="No tasks in this project yet." />}
      {data && data.length > 0 && (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Priority</TableHead>
                <TableHead>Due</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((t) => (
                <TableRow key={t.id}>
                  <TableCell>
                    <Link to={`/tasks/${t.id}`} className="font-medium hover:underline">
                      {t.title}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={t.status} />
                  </TableCell>
                  <TableCell>{PRIORITY_LABEL[t.priority]}</TableCell>
                  <TableCell className="text-muted-foreground">{formatDate(t.due_date)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>New task</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="t-title">Title</Label>
              <Input id="t-title" value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Priority</Label>
              <Select value={priority} onValueChange={setPriority}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(['low', 'medium', 'high', 'urgent'] as const).map((p) => (
                    <SelectItem key={p} value={p}>
                      {PRIORITY_LABEL[p]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button disabled={!title.trim() || create.isPending} onClick={() => create.mutate()}>
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function MembersTab({
  projectId,
  ownerId,
  canEdit,
}: {
  projectId: string
  ownerId: string
  canEdit: boolean
}) {
  const qc = useQueryClient()
  const { data: members, isLoading } = useQuery({
    queryKey: ['project-members', projectId],
    queryFn: () => api<ProjectMember[]>(`/api/projects/${projectId}/members`),
  })
  const { data: users } = useQuery({
    queryKey: ['users'],
    queryFn: () => api<User[]>('/api/users'),
    enabled: canEdit,
  })
  const [pick, setPick] = useState('')

  const mutateMember = (method: 'PUT' | 'DELETE') => ({
    onSuccess: () => qc.invalidateQueries({ queryKey: ['project-members', projectId] }),
    onError: (e: unknown) => toast.error(e instanceof ApiError ? e.message : 'Failed'),
    mutationFn: (userId: string) =>
      api(`/api/projects/${projectId}/members/${userId}`, { method }),
  })
  const add = useMutation(mutateMember('PUT'))
  const remove = useMutation(mutateMember('DELETE'))

  const memberIds = new Set(members?.map((m) => m.user.id))

  if (isLoading) return <Loading />

  return (
    <div className="max-w-xl space-y-4">
      <ul className="divide-y rounded-lg border">
        {members?.map((m) => (
          <li key={m.user.id} className="flex items-center justify-between px-3 py-2 text-sm">
            <div>
              <span className="font-medium">{m.user.full_name}</span>{' '}
              <span className="text-muted-foreground">· {m.user.email}</span>
              {m.user.id === ownerId && (
                <Badge variant="secondary" className="ml-2">
                  Owner
                </Badge>
              )}
            </div>
            {canEdit && m.user.id !== ownerId && (
              <button
                className="text-muted-foreground hover:text-destructive"
                onClick={() => remove.mutate(m.user.id)}
              >
                <X className="size-4" />
              </button>
            )}
          </li>
        ))}
      </ul>
      {canEdit && (
        <div className="flex gap-2">
          <Select value={pick} onValueChange={setPick}>
            <SelectTrigger className="w-64">
              <SelectValue placeholder="Add a member" />
            </SelectTrigger>
            <SelectContent>
              {users
                ?.filter((u) => !memberIds.has(u.id))
                .map((u) => (
                  <SelectItem key={u.id} value={u.id}>
                    {u.full_name} ({u.email})
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
          <Button
            size="sm"
            variant="outline"
            disabled={!pick || add.isPending}
            onClick={() => {
              add.mutate(pick)
              setPick('')
            }}
          >
            Add
          </Button>
        </div>
      )}
    </div>
  )
}

function SettingsTab({ project }: { project: Project }) {
  const qc = useQueryClient()
  const [name, setName] = useState(project.name)
  const [description, setDescription] = useState(project.description)
  const [ownerId, setOwnerId] = useState(project.owner_id)

  const { data: users } = useQuery({
    queryKey: ['users'],
    queryFn: () => api<User[]>('/api/users'),
  })

  const save = useMutation({
    mutationFn: () =>
      api(`/api/projects/${project.id}`, {
        method: 'PATCH',
        body: { name, description, owner_id: ownerId },
      }),
    onSuccess: () => {
      toast.success('Saved')
      qc.invalidateQueries({ queryKey: ['project', project.id] })
      qc.invalidateQueries({ queryKey: ['projects'] })
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : 'Failed'),
  })

  return (
    <div className="max-w-lg space-y-4">
      <div className="space-y-1.5">
        <Label>Name</Label>
        <Input value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="space-y-1.5">
        <Label>Description</Label>
        <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={4} />
      </div>
      <div className="space-y-1.5">
        <Label>Owner</Label>
        <Select value={ownerId} onValueChange={setOwnerId}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {users?.map((u) => (
              <SelectItem key={u.id} value={u.id}>
                {u.full_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <Button disabled={save.isPending} onClick={() => save.mutate()}>
        Save changes
      </Button>
    </div>
  )
}
