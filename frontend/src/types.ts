export type Role = 'manager' | 'member'
export type TaskStatus = 'backlog' | 'in_progress' | 'in_review' | 'done' | 'blocked'
export type TaskPriority = 'low' | 'medium' | 'high' | 'urgent'
export type TaskEventType =
  | 'created'
  | 'field_changed'
  | 'status_changed'
  | 'assigned'
  | 'unassigned'
  | 'dependency_added'
  | 'dependency_removed'
  | 'commented'

export interface User {
  id: string
  email: string
  full_name: string
  role: Role
  is_active: boolean
  created_at: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface Project {
  id: string
  key: string
  name: string
  description: string
  owner_id: string
  owner: User
  is_archived: boolean
  created_at: string
  updated_at: string
}

export interface ProjectMember {
  user: User
  member_since: string
}

export interface Invitation {
  id: string
  email: string
  role: Role
  invited_by_id: string
  expires_at: string
  accepted_at: string | null
  created_at: string
}
export interface InvitationCreated extends Invitation {
  accept_url: string
}

export interface TaskRef {
  id: string
  title: string
  status: TaskStatus
}

export interface Task {
  id: string
  project_id: string
  title: string
  description: string
  priority: TaskPriority
  status: TaskStatus
  blocked_from_status: TaskStatus | null
  due_date: string | null
  created_by_id: string
  created_at: string
  updated_at: string
  completed_at: string | null
}

export interface TaskDetail extends Task {
  assignees: User[]
  dependencies: TaskRef[]
  blocked_by_unfinished_dependency: boolean
  allowed_transitions: TaskStatus[]
}

export interface TaskListItem extends Task {
  project_key: string
  project_name: string
  assignees: User[]
}

export interface TaskPage {
  items: TaskListItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface TaskEvent {
  id: string
  event_type: TaskEventType
  field: string | null
  old_value: string | null
  new_value: string | null
  body: string | null
  created_at: string
  actor: User | null
}

export interface BulkItemResult {
  task_id: string
  ok: boolean
  error: string | null
}
export interface BulkResult {
  results: BulkItemResult[]
  succeeded: number
  failed: number
}

export interface DashboardHeadline {
  open: number
  overdue: number
  due_this_week: number
  completed_this_week: number
}
export interface StatusCount {
  status: TaskStatus
  count: number
}
export interface AssigneeCount {
  user: User | null
  count: number
}
export interface WeekCompletions {
  week_start: string
  count: number
}
export interface Dashboard {
  headline: DashboardHeadline
  by_status: StatusCount[]
  by_assignee: AssigneeCount[]
  completions_last_8_weeks: WeekCompletions[]
}

export interface AlertItem {
  id: string
  title: string
  project_id: string
  project_key: string
  status: TaskStatus
  priority: TaskPriority
  due_date: string
  days_overdue: number
}
export interface AlertsResponse {
  count: number
  items: AlertItem[]
}
