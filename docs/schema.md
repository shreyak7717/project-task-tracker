# Schema (draft)

Migrations: `backend/alembic/versions/`. State after Session 5 (the last
session to touch the schema) — nothing added or changed since; the later
sessions (archiving guard, dashboard/alerts scoping, task-list filters) were
all query-logic changes against this same schema, not migrations.

## Tables

### users
| column | type | notes |
|---|---|---|
| id | uuid | pk, app-generated (`uuid4`) |
| email | varchar(255) | unique, indexed, normalised (trim + lowercase) |
| hashed_password | varchar(255) | bcrypt |
| full_name | varchar(255) | |
| role | varchar(20) | `manager` \| `member` (enum in app, not DB) |
| is_active | bool | soft deactivation; blocks all auth |
| created_at | timestamptz | server default `now()` |

### invitations
| column | type | notes |
|---|---|---|
| id | uuid | pk |
| email | varchar(255) | indexed, normalised, NOT unique (re-invite after expiry) |
| role | varchar(20) | always `member` this version |
| invited_by_id | uuid | fk users.id |
| token_hash | varchar(64) | unique; SHA-256 of the one-time token (raw never stored) |
| expires_at | timestamptz | |
| accepted_at | timestamptz | null until accepted → single-use |
| accepted_user_id | uuid | fk users.id, null until accepted |
| created_at | timestamptz | |

### projects
| column | type | notes |
|---|---|---|
| id | uuid | pk |
| key | varchar(10) | unique, indexed, `^[A-Z][A-Z0-9]{1,9}$`, immutable after creation |
| name | varchar(200) | |
| description | text | |
| owner_id | uuid | fk users.id |
| is_archived | bool | indexed; excludes from default lists |
| created_at / updated_at | timestamptz | |

### project_memberships
`(project_id, user_id)` unique. Join table for users↔projects (M:N). `created_at`.
Owner is always a member. Cascade-deletes with the project or user.

### tasks
| column | type | notes |
|---|---|---|
| id | uuid | pk |
| project_id | uuid | fk projects.id, `ON DELETE CASCADE`, indexed |
| title | varchar(300) | |
| description | text | |
| priority | varchar(20) | enum in app: low/medium/high/urgent, indexed |
| status | varchar(20) | enum: backlog/in_progress/in_review/done/blocked, indexed |
| blocked_from_status | varchar(20) | nullable; the status to return to on unblock |
| due_date | date | nullable, indexed |
| created_by_id | uuid | fk users.id |
| completed_at | timestamptz | nullable; set on entering Done, cleared on reopen |
| created_at / updated_at | timestamptz | |

### task_dependencies
`task_id` (blocked) + `depends_on_task_id` (blocker). Unique pair
(`uq_dependency_pair`), check `task_id <> depends_on_task_id`
(`ck_dependency_not_self`). Both FKs cascade. Self-referential M:N on tasks.
Same-project rule is enforced in the app.

### task_assignees
`(task_id, user_id)` unique. Join table for tasks↔users (M:N). `assigned_at`.
Indexes: `ix_task_assignees_task_id` (a task's assignees) and, since Session 4,
a composite `ix_task_assignees_user_id_task_id` (migration `792e10ebcd05`) —
covers "tasks assigned to user X" (the `/api/me/tasks` hot path and the assignee
filter) as an index-only scan; it replaced the single-column `user_id` index.

### task_events  (append-only — no update/delete path anywhere)
| column | type | notes |
|---|---|---|
| id | uuid | pk |
| seq | bigint | Postgres `IDENTITY`, unique — the timeline sort key |
| task_id | uuid | fk tasks.id, cascade, indexed |
| actor_id | uuid | fk users.id, nullable (null = system) |
| event_type | varchar(30) | created / field_changed / status_changed / dependency_added / dependency_removed / assigned / unassigned / commented |
| field | varchar(50) | nullable |
| old_value / new_value | text | nullable |
| body | text | nullable (comment text) |
| created_at | timestamptz | indexed |

### alert_dismissals
`(task_id, user_id)` unique (`uq_dismissal_task_user`). `dismissed_due_date` =
the task's due date at the moment of dismissal. An overdue task shows an alert
for a user unless a dismissal row exists whose `dismissed_due_date` still equals
the task's *current* `due_date` — so changing the due date resurfaces the alert
with no trigger or cross-feature coupling. Written with `INSERT … ON CONFLICT …
DO UPDATE` (idempotent, concurrency-safe).

## Relationship types

- **One-to-many:** users→projects (owner), users→tasks (creator),
  projects→tasks, tasks→task_events, invitations→users (accepted_user).
- **Many-to-many via explicit join tables** (they carry columns and/or we write
  history when they change): users↔projects (`project_memberships`),
  tasks↔users (`task_assignees`), tasks↔tasks (`task_dependencies`).

## Constraints: database vs application

- **Database:** PKs, FKs, `ON DELETE CASCADE` on children, unique constraints
  (email, token_hash, every join pair, `task_events.seq`), no-self-dependency
  check.
- **Application:** the role and status/priority enums are stored as `varchar`
  and validated by Pydantic + the domain layer (so adding a value is a code
  change, not a locking migration). Cross-row rules — "an assignee must be a
  project member", "a blocking task must be Done before this task can be Done",
  "a blocker must be in the same project" — are application logic; they're ugly
  or impossible as DB constraints and need friendly error messages.

## Deliberate denormalisation

- `tasks.completed_at` — derivable from the event log; stored so the 8-week
  completions chart and "completed this week" are indexed range scans.
- `tasks.blocked_from_status` — reconstructable from the last status-change
  event; stored so unblock is a single field read.

## What breaks first at 100x data

The cross-project task list (`services/task_query.py`, Goal 6): `ILIKE` text
search + several optional filters + sort + paginated total count. At 100x:
- `ILIKE '%term%'` can't use a b-tree index → needs Postgres full-text
  (`tsvector` column + GIN index, kept current by a trigger).
- `SELECT count(*)` over the filtered set for `total` gets expensive → switch to
  an estimated count or keyset (cursor) pagination and drop the exact total.
- The `assignee_id` / `unassigned` subqueries are fine now (the composite index
  covers them) but a very wide "all overdue across the portfolio" scan would
  want a partial index `WHERE status <> 'done'` on `(due_date)`.

Dashboard aggregates (Goal 8) are next → move from live `GROUP BY` to a
cached/materialised summary refreshed on a schedule.
