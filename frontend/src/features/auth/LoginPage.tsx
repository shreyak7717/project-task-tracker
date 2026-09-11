import { zodResolver } from '@hookform/resolvers/zod'
import { Bell, LayoutDashboard, ListTodo, Users } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Navigate, useLocation } from 'react-router-dom'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError } from '@/lib/api'
import { useAuth } from '@/lib/auth'

const FEATURES = [
  { icon: LayoutDashboard, text: 'One dashboard for every project you’re on' },
  { icon: ListTodo, text: 'Full task lifecycle, from backlog to done' },
  { icon: Users, text: 'See who’s on what, at a glance' },
  { icon: Bell, text: 'Never miss something overdue' },
]

const schema = z.object({
  email: z.string().email('Enter a valid email'),
  password: z.string().min(1, 'Required'),
})
type Form = z.infer<typeof schema>

export function LoginPage() {
  const { user, login } = useAuth()
  const location = useLocation()
  const [error, setError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Form>({ resolver: zodResolver(schema) })

  if (user) {
    const to =
      (location.state as { from?: string } | null)?.from && location.state.from !== '/login'
        ? location.state.from
        : '/'
    return <Navigate to={to} replace />
  }

  const onSubmit = async (values: Form) => {
    setError(null)
    try {
      await login(values.email, values.password)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Login failed')
    }
  }

  return (
    <div className="flex min-h-screen">
      <div className="relative hidden w-1/2 flex-col justify-between overflow-hidden bg-primary p-10 text-primary-foreground lg:flex">
        <div className="pointer-events-none absolute -right-24 -top-24 size-72 rounded-full bg-white/10" />
        <div className="pointer-events-none absolute -bottom-32 -left-16 size-80 rounded-full bg-white/5" />

        <div className="relative flex items-center gap-2 text-lg font-semibold">
          <span className="grid size-9 place-items-center rounded-lg bg-white/15">
            <LayoutDashboard className="size-5" />
          </span>
          Busy InfoTech
        </div>

        <div className="relative space-y-8">
          <div>
            <h1 className="text-3xl font-semibold leading-tight">Project &amp; Task Tracker</h1>
            <p className="mt-2 max-w-sm text-primary-foreground/80">
              Plan, assign, and ship — one board for the whole team.
            </p>
          </div>
          <ul className="space-y-3">
            {FEATURES.map(({ icon: Icon, text }) => (
              <li
                key={text}
                className="flex items-center gap-3 text-sm text-primary-foreground/90"
              >
                <span className="grid size-7 shrink-0 place-items-center rounded-md bg-white/10">
                  <Icon className="size-4" />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-primary-foreground/60">
          Built for the Busy InfoTech take-home assignment.
        </p>
      </div>

      <div className="flex flex-1 items-center justify-center bg-muted/30 p-4">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2 text-lg font-semibold lg:hidden">
            <span className="grid size-9 place-items-center rounded-lg bg-primary text-primary-foreground">
              <LayoutDashboard className="size-5" />
            </span>
            Busy InfoTech
          </div>

          <h2 className="text-xl font-semibold tracking-tight">Sign in</h2>
          <p className="mt-1 text-sm text-muted-foreground">Welcome back to your Task Tracker</p>

          <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" autoComplete="username" {...register('email')} />
              {errors.email && (
                <p className="text-xs text-destructive">{errors.email.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                {...register('password')}
              />
              {errors.password && (
                <p className="text-xs text-destructive">{errors.password.message}</p>
              )}
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </div>
      </div>
    </div>
  )
}
