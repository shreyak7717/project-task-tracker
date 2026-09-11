import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarDays, UserRound } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { z } from 'zod'

import { EmptyState, ErrorState, Loading, PageHeader } from '@/components/common'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import { Textarea } from '@/components/ui/textarea'
import { api, ApiError } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { avatarColor, formatDate } from '@/lib/format'
import type { Project, User } from '@/types'

const schema = z.object({
  key: z
    .string()
    .trim()
    .regex(/^[A-Za-z][A-Za-z0-9]{1,9}$/, '2–10 letters/digits, starting with a letter'),
  name: z.string().min(1).max(200),
  description: z.string().max(5000).optional(),
  owner_id: z.string().uuid('Pick an owner'),
})
type Form = z.infer<typeof schema>

function NewProjectDialog() {
  const [open, setOpen] = useState(false)
  const qc = useQueryClient()
  const { data: users } = useQuery({
    queryKey: ['users'],
    queryFn: () => api<User[]>('/api/users'),
    enabled: open,
  })
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<Form>({ resolver: zodResolver(schema) })

  const create = useMutation({
    mutationFn: (values: Form) =>
      api<Project>('/api/projects', {
        method: 'POST',
        body: { ...values, key: values.key.toUpperCase(), description: values.description ?? '' },
      }),
    onSuccess: () => {
      toast.success('Project created')
      qc.invalidateQueries({ queryKey: ['projects'] })
      setOpen(false)
      reset()
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : 'Failed to create project'),
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button onClick={() => setOpen(true)}>New project</Button>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New project</DialogTitle>
          <DialogDescription>The key can’t be changed later.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit((v) => create.mutate(v))} className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="key">Key</Label>
              <Input id="key" placeholder="ACME" {...register('key')} />
            </div>
            <div className="col-span-2 space-y-1.5">
              <Label htmlFor="name">Name</Label>
              <Input id="name" {...register('name')} />
            </div>
          </div>
          {(errors.key || errors.name) && (
            <p className="text-xs text-destructive">{errors.key?.message ?? errors.name?.message}</p>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" {...register('description')} />
          </div>
          <div className="space-y-1.5">
            <Label>Owner</Label>
            <Select value={watch('owner_id')} onValueChange={(v) => setValue('owner_id', v)}>
              <SelectTrigger>
                <SelectValue placeholder="Select a user" />
              </SelectTrigger>
              <SelectContent>
                {users?.map((u) => (
                  <SelectItem key={u.id} value={u.id}>
                    {u.full_name} ({u.email})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.owner_id && (
              <p className="text-xs text-destructive">{errors.owner_id.message}</p>
            )}
          </div>
          <DialogFooter>
            <Button type="submit" disabled={isSubmitting || create.isPending}>
              Create
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function ProjectsPage() {
  const { user } = useAuth()
  const isManager = user?.role === 'manager'
  const [includeArchived, setIncludeArchived] = useState(false)
  const qc = useQueryClient()

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['projects', { includeArchived }],
    queryFn: () =>
      api<Project[]>('/api/projects', { params: { include_archived: includeArchived } }),
  })

  const archive = useMutation({
    mutationFn: ({ id, archived }: { id: string; archived: boolean }) =>
      api(`/api/projects/${id}/${archived ? 'restore' : 'archive'}`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
    onError: (e) => toast.error(e instanceof ApiError ? e.message : 'Failed'),
  })

  return (
    <div>
      <PageHeader
        title="Projects"
        description={isManager ? 'All projects' : 'Projects you belong to'}
        action={isManager ? <NewProjectDialog /> : undefined}
      />

      <label className="mb-3 flex w-fit items-center gap-2 text-sm text-muted-foreground">
        <Checkbox
          checked={includeArchived}
          onCheckedChange={(v) => setIncludeArchived(v === true)}
        />
        Show archived
      </label>

      {isLoading && <Loading />}
      {error && <ErrorState error={error} retry={() => void refetch()} />}
      {data && data.length === 0 && <EmptyState message="No projects yet." />}
      {data && data.length > 0 && (
        <div className="rounded-xl border shadow-sm">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Project</TableHead>
                <TableHead>Owner</TableHead>
                <TableHead>Created</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((p) => (
                <TableRow key={p.id}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <span
                        className={`grid size-9 shrink-0 place-items-center rounded-lg text-xs font-bold ${avatarColor(p.key)}`}
                      >
                        {p.key.slice(0, 2)}
                      </span>
                      <div>
                        <Link to={`/projects/${p.id}`} className="font-medium hover:underline">
                          {p.name}
                        </Link>
                        {p.is_archived && (
                          <Badge variant="secondary" className="ml-2">
                            Archived
                          </Badge>
                        )}
                        <div className="font-mono text-xs text-muted-foreground">{p.key}</div>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    <span className="flex items-center gap-1.5">
                      <UserRound className="size-3.5" />
                      {p.owner.full_name}
                    </span>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    <span className="flex items-center gap-1.5">
                      <CalendarDays className="size-3.5" />
                      {formatDate(p.created_at)}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">
                    {isManager && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => archive.mutate({ id: p.id, archived: p.is_archived })}
                      >
                        {p.is_archived ? 'Restore' : 'Archive'}
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
