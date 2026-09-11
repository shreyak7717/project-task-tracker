Decisions

Log the decisions that materially shaped this codebase — where a real alternative existed and the choice affected architecture, security, correctness, maintainability, or an important product behavior.

For each decision: what was chosen, what was rejected, and why. Decisions that changed during implementation are explicitly marked with Later reversed:.

Decision 1 — API + SPA split, not a single full-stack framework

Chose: standalone FastAPI JSON API + a separate React SPA.

Rejected: Next.js / a Django-templated app rendering HTML.

Why: fastest in Python and TypeScript separately; a hard HTTP boundary makes "the moving pieces and how they talk" explicit and keeps the API independently testable. Cost accepted: CORS, token transport, and two deploys.

Decision 2 — Invitation-based accounts, no public sign-up

Chose: accounts exist only via a manager-issued invitation. The invitee sets their own name + password when accepting a one-time, hashed, expiring token. The first manager comes from a seed script.

Rejected: open self-registration defaulting to member; or a manager endpoint that directly creates a user with a manager-chosen password.

Why: this is an internal tool for known employees, so open sign-up is inappropriate. Direct creation would mean the manager knows everyone's initial password; invitation keeps the credential with its owner. Only the SHA-256 hash of the invitation token is stored, so a database leak does not yield working invitations.

Later reversed: yes — the original plan was manager-creates-user directly; it was changed to token invitations before implementation.

Decision 3 — Role is in the JWT, but the DB row is authoritative

Chose: get_current_user decodes the token, then loads the users row by sub and reads role from that row. The role claim is never trusted for authorization.

Rejected: trusting the verified role claim to avoid the database lookup.

Why: access changes need to take effect before token expiry. A demotion or deactivation should not leave an already-issued token with effective old permissions. Tests cover a forged role=manager claim and a deactivated user's live token.

Decision 4 — Stateless refresh tokens, no server-side session store

Chose: refresh tokens are JWTs with a longer expiry and type=refresh, with no table of issued/revoked tokens.

Rejected: persisting refresh tokens for individual revocation.

Why: time budget. The trade-off is explicit: a specific refresh token cannot be force-revoked before its expiry. Deactivation still blocks access-token use immediately through the DB-authoritative user check. A production version could add a revocation list keyed by token ID.

Decision 5 — Service layer separate from routers

Chose: app/services/ contains domain logic without FastAPI imports and raises typed ServiceErrors; app/routers/ stays thin; schemas are split by domain. ORM models remain in one app/models.py.

Rejected: putting domain logic directly in route handlers.

Why: the important rules — state transitions, timeline writing, assignment validation, bulk processing, and visibility — need to be readable and testable without going through HTTP. Thin routers also keep the same rules reusable across normal and bulk endpoints.

Decision 6 — Real Postgres tests, not SQLite

Chose: pytest runs against a real Postgres test database, with each test isolated through a transaction/savepoint strategy.

Rejected: SQLite in-memory tests.

Why: the application relies on Postgres behavior such as UUIDs, ON DELETE CASCADE, SELECT ... FOR UPDATE, check constraints, and IDENTITY. SQLite could make tests pass while hiding differences that matter in the deployed database. The cost is requiring Postgres/Docker for the test environment.

Decision 7 — Timeline ordering uses a monotonic identity column

Chose: task_events.seq (Postgres IDENTITY) is the timeline sort key.

Rejected: ORDER BY created_at, id.

Why: created_at defaults to now(), which can give multiple events created in the same transaction the same timestamp, while UUIDs provide no meaningful chronological tiebreaker. Testing exposed scrambled ordering. A monotonic integer is a better ordering key for an append-only event log.

Later reversed: yes — the original timestamp + UUID ordering was replaced after testing showed it was not deterministic enough.

Decision 8 — Bulk actions use per-task savepoints

Chose: each task in a bulk request runs inside its own savepoint. A failed task is rolled back independently and reported as {task_id, ok: false, error}, while successful tasks remain committed.

Rejected: all-or-nothing transaction semantics for the entire batch, or duplicating all validation in a pre-validation pass.

Why: the requirement is to report per-task success/failure rather than fail the whole batch. Different tasks in the same request can have different legal outcomes, such as lifecycle transitions blocked by dependencies. Savepoints let bulk processing reuse the real task mutation services instead of duplicating their rules.

Decision 9 — One query builder for task list, CSV, and "assigned to me"

Chose: services/task_query.py builds one filtered SELECT; the normal list endpoint paginates it, CSV streams all matching rows, and /api/me/tasks applies the caller's assignee filter.

Rejected: separate query implementations for each endpoint.

Why: visibility, search, filters, and overdue logic are security- and correctness-sensitive. Centralizing them reduces the chance that one endpoint accidentally exposes tasks or behaves differently from another. One implementation also means one core set of tests.

Decision 10 — Search uses ILIKE now; full-text search can come later

Chose: case-insensitive substring matching on title + description using escaped ILIKE.

Rejected: adding Postgres full-text search (tsvector + GIN) from the start.

Why: at the expected scale of roughly a dozen projects, substring search is simple and sufficient. Full-text search would add schema/indexing complexity without a clear need. If scale or search requirements grow, the query can be replaced behind the same task-query boundary.

Decision 11 — Dashboard and alert date maths use one UTC reference

Chose: dashboard and alert services compute one UTC today reference per request and pass it into their queries as a bind parameter. The rolling chart buckets are derived from that same reference.

Rejected: letting Postgres independently evaluate "today" with CURRENT_DATE, or mixing database and Python date calculations.

Why: the database session timezone is not guaranteed to match the application's intended timezone. One UTC reference keeps headline numbers, overdue calculations, alert filtering, and chart buckets consistent and avoids boundary-day discrepancies.

Decision 12 — Eight-week completion chart uses rolling 7-day windows

Chose: eight explicit 7-day windows anchored to the current UTC date, with completions assigned to those windows.

Rejected: GROUP BY date_trunc('week', completed_at).

Why: date_trunc('week') produces calendar weeks, while the dashboard requirement is a rolling view of the last eight weeks. Rolling windows also make the current dashboard bucket line up with the definition of "completed this week" used by the headline metric.

Decision 13 — Overdue-alert dismissal stores the due date

Chose: alert_dismissals stores the task's due date at the moment of dismissal. An alert resurfaces when the task's current due date no longer matches the stored dismissal date. Dismissal uses an upsert on the unique (task_id, user_id) pair.

Rejected: a simple boolean dismissed flag that would need to be cleared whenever the task's due date changes.

Why: the stored-value approach needs no trigger and no coupling from task updates into the alert feature. Changing the due date naturally makes the old dismissal stale, so the alert reappears. The database upsert also makes repeated dismissal idempotent and concurrency-safe.

Decision 14 — Archiving freezes task work, while comments/dependencies remain available

Chose: archiving a project blocks creating, editing, transitioning, and assigning tasks in that project. A shared ensure_project_active() service check enforces the rule, so bulk actions inherit it automatically. Comments and dependency changes remain allowed for historical/reference discussion.

Rejected: treating archive as only a list-visibility flag; or freezing every kind of task mutation including comments and dependencies.

Why: live testing showed that merely hiding an archived project still allowed its work to be changed, which made "archived" misleading. Freezing work makes the state meaningful while keeping the discussion/reference trail usable. Centralizing the guard avoids duplicated checks across routers and bulk actions.

Later reversed: yes — the original archive behavior was "hide but keep fully editable." Live testing changed the decision to a true task-work freeze.

Decision 15 — Dashboard defaults to team scope; "My work" is opt-in

Chose: the dashboard defaults to the existing portfolio/team scope. scope=mine adds a second filter for tasks assigned to the current user, composed with the existing project-visibility filter.

Rejected: changing only the header wording without implementing personal scope; or making "My work" the default.

Why: the team-wide view is useful for portfolio health and is consistent with the manager's portfolio visibility. The personal view is useful as an opt-in narrower slice. Keeping the filtering in the same scoped query path avoids duplicating visibility logic.

Decision 16 — Alerts: members see only their own; managers keep the full portfolio

Chose: a manager's alert list stays portfolio-wide — every overdue, unfinished task across every visible project. A member's list is narrowed further, to only tasks assigned to them specifically. The list also now flags which rows the caller can actually dismiss (assigned_to_me), so the frontend can hide the Dismiss action instead of just letting it fail.

Rejected: keeping the original member behavior — every overdue task in a member's visible projects, regardless of assignee, with dismissal gated by assignment on the backend but unenforced in the UI.

Why: live testing surfaced the actual cost of the original design: a member's list was mostly tasks they had no way to act on, and the frontend offered a Dismiss button on all of them anyway, which just 403'd silently when clicked. Once the UI was fixed to show which rows were actually dismissible, it became clear a member's overdue list should just be their own work — a manager still needs the portfolio view for cross-team visibility, but a member doesn't have an equivalent need for it.

Later reversed: yes — the original portfolio-wide member scope (same reasoning as the Dashboard's team-wide default) was narrowed to assignment-only for members after live testing.