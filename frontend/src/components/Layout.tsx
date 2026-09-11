import { useQuery } from '@tanstack/react-query'
import {
  Bell,
  FolderKanban,
  LayoutDashboard,
  ListTodo,
  LogOut,
  Menu,
  UserRound,
} from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { cn } from '@/lib/utils'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/my-tasks', label: 'My Tasks', icon: ListTodo, end: true },
  { to: '/tasks', label: 'All Tasks', icon: ListTodo, end: true },
  { to: '/projects', label: 'Projects', icon: FolderKanban },
  { to: '/alerts', label: 'Alerts', icon: Bell, badge: true },
]

function AlertBadge() {
  const { data } = useQuery({
    queryKey: ['alert-count'],
    queryFn: () => api<{ count: number }>('/api/alerts/count'),
    refetchInterval: 60_000,
  })
  if (!data?.count) return null
  return (
    <span className="ml-auto rounded-full bg-destructive px-1.5 text-xs font-semibold text-destructive-foreground">
      {data.count}
    </span>
  )
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-1">
      {NAV.map(({ to, label, icon: Icon, end, badge }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
              isActive
                ? 'bg-primary/10 text-primary'
                : 'text-muted-foreground hover:bg-accent hover:text-foreground',
            )
          }
        >
          <Icon className="size-4" />
          {label}
          {badge && <AlertBadge />}
        </NavLink>
      ))}
    </nav>
  )
}

export function Layout() {
  const { user, logout } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="hidden w-60 shrink-0 flex-col border-r bg-sidebar p-4 md:flex">
        <div className="mb-6 px-2 text-lg font-semibold">Task Tracker</div>
        <NavItems />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="absolute left-0 top-0 flex h-full w-64 flex-col border-r bg-sidebar p-4">
            <div className="mb-6 px-2 text-lg font-semibold">Task Tracker</div>
            <NavItems onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center gap-3 border-b px-4">
          <button
            className="rounded-md p-1.5 hover:bg-accent md:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="Open menu"
          >
            <Menu className="size-5" />
          </button>
          <div className="ml-auto">
            <DropdownMenu>
              <DropdownMenuTrigger className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent">
                <span className="grid size-7 place-items-center rounded-full bg-primary/10 text-primary">
                  <UserRound className="size-4" />
                </span>
                <span className="hidden sm:inline">{user?.full_name}</span>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52">
                <DropdownMenuLabel>
                  <div className="font-medium">{user?.full_name}</div>
                  <div className="text-xs font-normal capitalize text-muted-foreground">
                    {user?.role} · {user?.email}
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={logout} className="text-destructive">
                  <LogOut className="size-4" />
                  Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <main className="min-w-0 flex-1 p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
