# Submission

Fill this in and commit it. This is the first file we open.

## Links

- **GitHub repository:** https://github.com/shreyak7717/project-task-tracker
- **Live application:** https://project-task-tracker-rho.vercel.app
  (API: https://task-tracker-api-fqev.onrender.com)

## Notes for the reviewer

The backend is on Render's free tier, which spins down after inactivity — the first request after a while can take up to ~50 seconds while it wakes back up; everything after that is normal speed. The live app is pre-seeded with demo data (4 projects, 5 members, ~28 tasks across every status/priority) so there's something real to click through immediately — see credentials below.

## Demo credentials

| Role | Email | Password |
|------|-------|----------|
| Manager | manager@demo.com | DemoManager2026! |
| Member | alice@example.com  | password123 |
| Member | bob@example.com  | password123 |
| Member | carol@example.com | password123 |
| Member | dana@example.com | password123 |
| Member | evan@example.com | password123 |

## Stack

| Layer | What you used | Why |
|-------|---------------|-----|
| Frontend | React 19 + TypeScript + Vite, Tailwind v4 + shadcn/ui (hand-written components), TanStack Query, React Router, Recharts, React Hook Form + Zod | Fast dev loop, server state and client state kept clearly separate (TanStack Query vs. local state), typed forms validated the same shape the API expects |
| Backend | FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2, JWT auth (python-jose) | Async-capable but used sync SQLAlchemy for simplicity at this scale; Pydantic gives request/response validation for free; typed `ServiceError`s keep domain errors out of the HTTP layer |
| Database | PostgreSQL 16 (Neon in production) | Needed real Postgres behavior — savepoints, `ON CONFLICT` upserts, check constraints, `IDENTITY` columns — not just a generic SQL store |
| Hosting | Vercel (frontend) + Render (backend) + Neon (Postgres) | Free tiers that fit a take-home, deployed as three independent services matching the app's actual architecture |

## Goal checklist

Mark each honestly. Partial is fine — say what is partial.

| # | Goal | Status | Notes |
|---|------|--------|-------|
| 1 | Accounts & roles | Done | Invitation-only accounts (no public sign-up), manager/member roles, DB-authoritative role check (JWT `role` claim is never trusted for authorization) |
| 2 | Projects | Done | CRUD, membership, archive/restore, manager-only where it should be, member gets 404 (not 403) on a project they can't see |
| 3 | Tasks | Done | CRUD scoped to a project, same visibility rule as projects |
| 4 | Task lifecycle / state machine | Done | Explicit allowed-transitions table, illegal transitions rejected server-side and leave the task untouched, dependencies block `Done` |
| 5 | Assignment | Done | Assign/unassign, constrained to actual project members, atomic whole-set replacement |
| 6 | Cross-project search/filter/sort/pagination | Done | One shared query builder reused by the list endpoint, CSV export, and "assigned to me" |
| 7 | Bulk actions + CSV export | Done | Per-task savepoints with per-task success/failure reporting; CSV streams the same filtered set |
| 8 | Dashboard | Done | Headline counts, status breakdown, assignee breakdown, 8-week rolling completions chart; team-wide by default with an opt-in "my work" scope |
| 9 | Immutable audit history | Done (one honest caveat) | Append-only by application-code discipline — no edit/delete route or function exists anywhere, and a test proves it. Not enforced at the database level (no `REVOKE`/trigger), so a raw SQL statement could still mutate a row in theory |
| 10 | Overdue alerts | Done | Managers see the whole portfolio, members see only their own assigned tasks; dismissal requires being assigned even for managers; resurfaces automatically if the due date changes |

## How much time did you actually spend?

Approximately 14–16 hours of focused implementation and testing time, spread across the build sessions and final deployment/debugging. This includes backend implementation, frontend implementation, testing, deployment, live verification, and documentation.

## What would you do next, with another 12 hours?

I would focus on hardening the parts that are currently application-level rather than adding new product features:

1. Add database-level protection for the append-only task event log.
2. Add full graph-based dependency-cycle detection for multi-hop dependency chains.
3. Add refresh-token revocation so sessions can be explicitly invalidated.
4. Add rate limiting for login and invitation acceptance endpoints.

I would prioritize these over adding more UI features because the core product requirements are already implemented.

## What are you least happy with in this codebase, and why?

The main thing I'm least happy with is that immutable task history is enforced by application-code discipline rather than at the database level. There are no update/delete routes or service functions for task events, and this is covered by tests, but a sufficiently privileged raw SQL operation could still modify the table.

I also think the dependency-cycle validation could be stronger. The current implementation prevents self-dependencies and direct reverse pairs, but does not perform full multi-hop graph cycle detection. Both are reasonable for the scope of the take-home, but they would be the first areas I would strengthen before treating this as production-ready.
