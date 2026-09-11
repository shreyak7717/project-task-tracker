import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'

import { EmptyState, ErrorState, Loading, PageHeader, StatusBadge } from '@/components/common'
import { BulkBar } from '@/features/tasks/BulkBar'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api, apiBlob } from '@/lib/api'
import { ALL_PRIORITIES, ALL_STATUSES, formatDate, PRIORITY_LABEL, STATUS_LABEL } from '@/lib/format'
import type { Project, TaskPage } from '@/types'

const PAGE_SIZE = 25

export function TaskListPage({ mine = false }: { mine?: boolean }) {
  const [params, setParams] = useSearchParams()
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const searchTimer = useRef<number | undefined>(undefined)

  const q = params.get('q') ?? ''
  const status = params.get('status') ?? ''
  const priority = params.get('priority') ?? ''
  const projectId = params.get('project_id') ?? ''
  const overdue = params.get('overdue') === 'true'
  const sort = params.get('sort') ?? 'updated_at'
  const page = Number(params.get('page') ?? '1')

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    setParams(next)
    setSelected(new Set())
  }

  const queryParams = useMemo(
    () => ({
      q: q || undefined,
      status: status || undefined,
      priority: priority || undefined,
      project_id: projectId || undefined,
      overdue: overdue || undefined,
      sort,
      page,
      page_size: PAGE_SIZE,
    }),
    [q, status, priority, projectId, overdue, sort, page],
  )

  const path = mine ? '/api/me/tasks' : '/api/tasks'
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['tasks', path, queryParams],
    queryFn: () => api<TaskPage>(path, { params: queryParams }),
  })

  const { data: projects } = useQuery({
    queryKey: ['projects', { includeArchived: false }],
    queryFn: () => api<Project[]>('/api/projects'),
  })

  const qc = useQueryClient()
  const exportMutation = useMutation({
    mutationFn: async () => {
      const blob = await apiBlob('/api/tasks/export', { ...queryParams, page: undefined })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `tasks-${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    },
    onError: () => toast.error('Export failed'),
  })

  const rows = data?.items ?? []
  const allSelected = rows.length > 0 && rows.every((t) => selected.has(t.id))

  return (
    <div>
      <PageHeader
        title={mine ? 'My Tasks' : 'All Tasks'}
        description={mine ? 'Everything assigned to you' : 'Across every project you can see'}
        action={
          <Button
            variant="outline"
            onClick={() => exportMutation.mutate()}
            disabled={exportMutation.isPending}
          >
            <Download className="size-4" /> CSV
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Input
          placeholder="Search title or description…"
          defaultValue={q}
          onChange={(e) => {
            const v = e.target.value
            window.clearTimeout(searchTimer.current)
            searchTimer.current = window.setTimeout(() => setParam('q', v), 350)
          }}
          className="w-56"
        />
        {!mine && (
          <FilterSelect
            value={projectId}
            onChange={(v) => setParam('project_id', v)}
            placeholder="Project"
            options={(projects ?? []).map((p) => ({ value: p.id, label: p.key }))}
          />
        )}
        <FilterSelect
          value={status}
          onChange={(v) => setParam('status', v)}
          placeholder="Status"
          options={ALL_STATUSES.map((s) => ({ value: s, label: STATUS_LABEL[s] }))}
        />
        <FilterSelect
          value={priority}
          onChange={(v) => setParam('priority', v)}
          placeholder="Priority"
          options={ALL_PRIORITIES.map((p) => ({ value: p, label: PRIORITY_LABEL[p] }))}
        />
        <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <Checkbox
            checked={overdue}
            onCheckedChange={(v) => setParam('overdue', v === true ? 'true' : '')}
          />
          Overdue
        </label>
        <FilterSelect
          value={sort}
          onChange={(v) => setParam('sort', v)}
          placeholder="Sort"
          allowClear={false}
          options={[
            { value: 'updated_at', label: 'Last updated' },
            { value: 'due_date', label: 'Due date' },
            { value: 'priority', label: 'Priority' },
          ]}
        />
      </div>

      <BulkBar
        taskIds={[...selected]}
        projectId={projectId || undefined}
        onDone={() => {
          setSelected(new Set())
          qc.invalidateQueries({ queryKey: ['tasks'] })
        }}
        onClear={() => setSelected(new Set())}
      />

      {isLoading && <Loading />}
      {error && <ErrorState error={error} retry={() => void refetch()} />}
      {data && rows.length === 0 && <EmptyState message="No tasks match these filters." />}

      {data && rows.length > 0 && (
        <>
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8">
                    <Checkbox
                      checked={allSelected}
                      onCheckedChange={(v) =>
                        setSelected(v === true ? new Set(rows.map((t) => t.id)) : new Set())
                      }
                    />
                  </TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Project</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Assignees</TableHead>
                  <TableHead>Due</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((t) => (
                  <TableRow key={t.id} data-state={selected.has(t.id) ? 'selected' : undefined}>
                    <TableCell>
                      <Checkbox
                        checked={selected.has(t.id)}
                        onCheckedChange={(v) => {
                          const next = new Set(selected)
                          if (v === true) next.add(t.id)
                          else next.delete(t.id)
                          setSelected(next)
                        }}
                      />
                    </TableCell>
                    <TableCell>
                      <Link to={`/tasks/${t.id}`} className="font-medium hover:underline">
                        {t.title}
                      </Link>
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {t.project_key}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={t.status} />
                    </TableCell>
                    <TableCell className="capitalize">{PRIORITY_LABEL[t.priority]}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {t.assignees.map((a) => a.full_name.split(' ')[0]).join(', ') || '—'}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{formatDate(t.due_date)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <div className="mt-3 flex items-center justify-between text-sm text-muted-foreground">
            <span>
              {data.total} match{data.total === 1 ? '' : 'es'} · page {data.page} of{' '}
              {Math.max(data.pages, 1)}
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setParam('page', String(page - 1))}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= data.pages}
                onClick={() => setParam('page', String(page + 1))}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function FilterSelect({
  value,
  onChange,
  placeholder,
  options,
  allowClear = true,
}: {
  value: string
  onChange: (v: string) => void
  placeholder: string
  options: { value: string; label: string }[]
  allowClear?: boolean
}) {
  return (
    <Select
      value={value || '__all'}
      onValueChange={(v) => onChange(v === '__all' ? '' : v)}
    >
      <SelectTrigger className="w-40">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {allowClear && <SelectItem value="__all">{placeholder}: any</SelectItem>}
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
