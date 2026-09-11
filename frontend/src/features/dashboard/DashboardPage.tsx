import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ErrorState, Loading, PageHeader } from '@/components/common'
import { api } from '@/lib/api'
import { STATUS_LABEL } from '@/lib/format'
import type { Dashboard } from '@/types'

type Scope = 'team' | 'mine'

const CHART_COLORS = ['#4f7ce6', '#4fc48a', '#d8a13a', '#d76a3a', '#9b6fd8']

function Stat({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-sm text-muted-foreground">{label}</div>
        <div className={`mt-1 text-2xl font-semibold ${tone ?? ''}`}>{value}</div>
      </CardContent>
    </Card>
  )
}

export function DashboardPage() {
  const [scope, setScope] = useState<Scope>('team')
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['dashboard', scope],
    queryFn: () =>
      api<Dashboard>('/api/dashboard', { params: { scope: scope === 'mine' ? 'mine' : undefined } }),
  })

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description={scope === 'mine' ? 'Just your assigned work' : 'Every project you can see'}
        action={
          <Tabs value={scope} onValueChange={(v) => setScope(v as Scope)}>
            <TabsList>
              <TabsTrigger value="team">Team</TabsTrigger>
              <TabsTrigger value="mine">My work</TabsTrigger>
            </TabsList>
          </Tabs>
        }
      />
      {isLoading && <Loading rows={6} />}
      {error && <ErrorState error={error} retry={() => void refetch()} />}
      {data && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Stat label="Open tasks" value={data.headline.open} />
            <Stat
              label="Overdue"
              value={data.headline.overdue}
              tone={data.headline.overdue > 0 ? 'text-red-600' : undefined}
            />
            <Stat label="Due this week" value={data.headline.due_this_week} />
            <Stat label="Completed this week" value={data.headline.completed_this_week} />
          </div>

          <div className={scope === 'mine' ? 'grid gap-4' : 'grid gap-4 lg:grid-cols-2'}>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Tasks by status</CardTitle>
              </CardHeader>
              <CardContent className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={data.by_status.map((s) => ({
                      name: STATUS_LABEL[s.status],
                      count: s.count,
                    }))}
                  >
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="name" fontSize={12} />
                    <YAxis allowDecimals={false} fontSize={12} width={28} />
                    <Tooltip />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                      {data.by_status.map((_, i) => (
                        <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Doesn't mean much under "My work" — it would show co-assignees
                on your shared tasks rather than being "about you", so it's
                only shown for the team-wide view. */}
            {scope === 'team' && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Open tasks by assignee</CardTitle>
                </CardHeader>
                <CardContent className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      layout="vertical"
                      data={data.by_assignee
                        .slice(0, 8)
                        .map((a) => ({ name: a.user?.full_name ?? 'Unassigned', count: a.count }))}
                    >
                      <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                      <XAxis type="number" allowDecimals={false} fontSize={12} />
                      <YAxis type="category" dataKey="name" width={110} fontSize={12} />
                      <Tooltip />
                      <Bar dataKey="count" fill={CHART_COLORS[0]} radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            )}
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Completions — last 8 weeks</CardTitle>
            </CardHeader>
            <CardContent className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={data.completions_last_8_weeks.map((w) => ({
                    week: new Date(w.week_start).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                    }),
                    count: w.count,
                  }))}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="week" fontSize={12} />
                  <YAxis allowDecimals={false} fontSize={12} width={28} />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="count"
                    stroke={CHART_COLORS[1]}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
