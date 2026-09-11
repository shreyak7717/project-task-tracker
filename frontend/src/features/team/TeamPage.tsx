import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, Mail, UsersRound } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import { EmptyState, ErrorState, Loading, PageHeader } from '@/components/common'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api, ApiError } from '@/lib/api'
import { avatarColor, formatDate, initials } from '@/lib/format'
import type { Invitation, InvitationCreated, User } from '@/types'

const schema = z.object({ email: z.string().email('Enter a valid email') })
type Form = z.infer<typeof schema>

function InviteDialog() {
  const [open, setOpen] = useState(false)
  const [created, setCreated] = useState<InvitationCreated | null>(null)
  const qc = useQueryClient()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<Form>({ resolver: zodResolver(schema) })

  const invite = useMutation({
    mutationFn: (values: Form) =>
      api<InvitationCreated>('/api/users/invitations', { method: 'POST', body: values }),
    onSuccess: (inv) => {
      setCreated(inv)
      qc.invalidateQueries({ queryKey: ['invitations'] })
      reset()
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : 'Could not invite'),
  })

  const close = () => {
    setOpen(false)
    setCreated(null)
  }

  return (
    <Dialog open={open} onOpenChange={(o) => (o ? setOpen(true) : close())}>
      <Button onClick={() => setOpen(true)}>Invite member</Button>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Invite a member</DialogTitle>
          <DialogDescription>
            No email is sent yet — you'll get a one-time link to share manually.
          </DialogDescription>
        </DialogHeader>

        {!created ? (
          <form onSubmit={handleSubmit((v) => invite.mutate(v))} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="invite-email">Email</Label>
              <Input id="invite-email" type="email" {...register('email')} />
              {errors.email && (
                <p className="text-xs text-destructive">{errors.email.message}</p>
              )}
            </div>
            <DialogFooter>
              <Button type="submit" disabled={isSubmitting || invite.isPending}>
                Send invite
              </Button>
            </DialogFooter>
          </form>
        ) : (
          <div className="space-y-3">
            <p className="text-sm">
              Invitation created for <span className="font-medium">{created.email}</span>. Share
              this link with them (expires {formatDate(created.expires_at)}):
            </p>
            <div className="flex items-center gap-2 rounded-md border bg-muted p-2 text-xs">
              <span className="min-w-0 flex-1 truncate">{created.accept_url}</span>
              <button
                onClick={() => {
                  void navigator.clipboard.writeText(created.accept_url)
                  toast.success('Copied')
                }}
                aria-label="Copy link"
              >
                <Copy className="size-3.5" />
              </button>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={close}>
                Done
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

export function TeamPage() {
  const { data: users, isLoading, error, refetch } = useQuery({
    queryKey: ['users'],
    queryFn: () => api<User[]>('/api/users'),
  })
  const { data: invitations } = useQuery({
    queryKey: ['invitations'],
    queryFn: () => api<Invitation[]>('/api/users/invitations', { params: { status: 'pending' } }),
  })

  return (
    <div>
      <PageHeader title="Team" description="Everyone with access" action={<InviteDialog />} />

      {isLoading && <Loading />}
      {error && <ErrorState error={error} retry={() => void refetch()} />}
      {users && (
        <div className="mb-6 rounded-xl border shadow-sm">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Joined</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((u) => (
                <TableRow key={u.id}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-3">
                      <span
                        className={`grid size-8 shrink-0 place-items-center rounded-full text-xs font-bold ${avatarColor(u.full_name)}`}
                      >
                        {initials(u.full_name)}
                      </span>
                      {u.full_name}
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{u.email}</TableCell>
                  <TableCell>
                    <Badge variant={u.role === 'manager' ? 'default' : 'secondary'}>
                      {u.role}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{formatDate(u.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <h2 className="mb-2 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
        <UsersRound className="size-4" />
        Pending invitations
        {invitations && invitations.length > 0 && (
          <Badge variant="secondary" className="ml-0.5">
            {invitations.length}
          </Badge>
        )}
      </h2>
      {invitations && invitations.length === 0 && <EmptyState message="No pending invitations." />}
      {invitations && invitations.length > 0 && (
        <div className="rounded-xl border shadow-sm">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Sent</TableHead>
                <TableHead>Expires</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {invitations.map((inv) => (
                <TableRow key={inv.id}>
                  <TableCell>
                    <span className="flex items-center gap-1.5">
                      <Mail className="size-3.5 text-muted-foreground" />
                      {inv.email}
                    </span>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(inv.created_at)}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(inv.expires_at)}
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
