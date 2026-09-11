# Plan (draft)

## How the work was split

Seven sessions of roughly two hours, backend-first: the domain rules (state
machine, immutable history, permission model) are the risky part and everything
else depends on them.

1. Foundation + data model
2. Auth + RBAC
3. Projects + tasks + task lifecycle
4. Assignment, cross-project list/search, bulk actions, CSV export
5. Dashboard + overdue alerts (backend)
6. Frontend — all screens
7. Seed data, deploy, docs

"Sessions" are mine; the brief defines 10 numbered **goals** and asks how I split
the work. Mapping: S1 enables all; S2 → goal 1; S3 → goals 2, 3, 4 and part of
9; S4 → goals 5, 6, 7; S5 → goals 8, 10; S6 → all (UI); S7 → not a numbered
goal — seed data, deployment, and documentation.

The plan originally had six sessions (frontend as S5, dashboard/alerts folded
into an S6 with deploy+docs) — it grew to seven once dashboard/alerts moved
ahead of the frontend and deploy+docs turned out to be enough work on their
own. See "Estimated vs actual" below.

## Order and why

Schema first so migrations exist before code writes rows. Auth second — every
later endpoint needs `get_current_user` and the role gate. The task state
machine (S3) before bulk actions (S4), because a bulk action is "apply one
transition to many tasks" and reuses the same validation. Frontend after the API
is real so I'm not rebuilding against a moving contract.

## Estimated vs actual

| Session | Est | Actual | Notes |
|---|---|---|---|
| 1 Foundation | 2h | ~2h | Local Postgres already on 5432 → moved the container to 5433. One mislabeled first commit had to be redone so history stayed honest. |
| 2 Auth + RBAC | 2h | ~2h | Scope grew: switched from direct user creation to a full token-invitation flow (model + migration + accept endpoint + race handling); built the real-Postgres test harness. 35 tests. |
| 3 Projects + tasks + lifecycle | 2h | ~3h | State machine + immutable timeline + full CRUD + membership + ~45 new tests. Hit a real ordering bug — Postgres `now()` is per-transaction, so same-request timeline events collided; added an `IDENTITY` column. |
| 4 Assignment / list / bulk / CSV | 2.5h | ~2.5h | Assignment service, one shared task-query builder (search/filter/sort/paginate), bulk with per-task savepoints, streaming CSV. 33 new tests. Adopted `ruff format` repo-wide in one dedicated commit. |
| 5 Dashboard + alerts (backend) | 1.5h | ~2h | Reordered — did the last two backend goals (8, 10) before the frontend so the API is complete. UTC-anchored date maths, rolling-7-day chart buckets, alert resurfacing via a stored due date. 13 new tests. **Backend now covers all 10 goals.** |
| 6 Frontend — all screens | 3h | 2.5h | SPA scaffold (Vite/React/TS/Tailwind/shadcn, TanStack Query+Table, React Router), then projects UI, task list/detail/timeline/bulk/CSV UI, dashboard+alerts UI, team/invite UI. Wiring the frontend surfaced a few backend bugs, fixed in the same session: missing `Content-Disposition` exposure for cross-origin CSV download, a task-type mismatch, bulk-result dialog bugs, dialog overflow on long text. |
| 7 Seed data, deploy, docs | 2.5h | 1h | Rich demo seed data (`seed_demo.py`, 4 projects/5 members/~28 tasks, built through the real services so state machine + event log stay correct), Render blueprint for the API, Vercel SPA rewrite, demo seed wired to run on every deploy. |

## Post-completion fixes

after the plan above was "done" and the app was actually live on Vercel + Render — testing the real deployment (not just local) surfaced a handful of gaps that only show up once you're clicking through it as a real user would. Fixed in order found:

- **Invite-link dialog overflowing its box.** A long accept-invite URL blew past the dialog's width — a flex child needs `min-w-0` to truncate, but the dialog's own grid container needed the same fix first. Fixed in `dialog.tsx` (`grid-cols-1`), so every dialog in the app is covered, not just this one.
- **Archiving was purely cosmetic.** Reversed the original design (archive only hid a project from lists) to **Decision 14**: archiving now freezes task mutations — create/transition/assign/edit all 409; comments and dependencies stay open. One shared `ensure_project_active()` check, so bulk actions inherit it too.
- **Task lists didn't reflect the new freeze.** An archived-project task looked ordinary until a mutation 409'd. Task lists gained the same `include_archived` toggle Projects already had, plus an "Archived" badge — a follow-on UI fix, not its own numbered decision.
- **Dashboard read as personal when it was team-wide.** "Your portfolio at a glance" implied your work, but every number was team-wide. **Decision 15**: added an opt-in "My work" scope (`?scope=mine`), reusing the same visibility-filter pattern.
- **Saving a task gave no feedback.** "Save changes" completed silently. Added success toasts (`Task updated`, `Status updated`, etc.) matching the confirmation pattern already used elsewhere in the app.
- **Dashboard still counted frozen work.** The task-list fix didn't reach the dashboard's separate query path. Now unconditionally excludes archived-project tasks too — no toggle needed there.
- **Alerts offered Dismiss on rows you couldn't act on.** Portfolio-wide by design, but Dismiss was enabled on every row regardless of assignment, 403ing silently. The API now flags `assigned_to_me`; the frontend only shows Dismiss when true — folded into Decision 16 below.
- **A member's alert list was mostly noise.** Once "Not yours" made it visible, most of a member's list was rows they couldn't act on. **Decision 16**: members now see only their own assigned alerts; managers keep the full portfolio view — a partial reversal of the original design.
- **UI polish pass**, once everything worked end-to-end: a branded login page, the same brand mark carried into the sidebar/header, icon badges on the dashboard's stats, and colored initials avatars on Projects/Team (shared `avatarColor()`/`initials()` helpers).
- **Invitations were never actually delivered.** The accept link only ever showed up in the API response — nothing was emailed. Tried Resend first (its zero-setup shared sender needs no domain), but its shared sender only delivers to the account owner's own address, not arbitrary recipients — no good for actually inviting someone. Switched to SendGrid (single-sender verification: verify one email you own, then send to anyone). Email is strictly best-effort — the invitation is committed to the DB before any send is attempted, so a missing key or a provider outage never affects invitation creation or acceptance; `accept_url` keeps being returned either way, same as before.

See `decisions.md` for the full reasoning behind each of these.

## Final verification

Before writing up the submission, ran a goal-by-goal audit against the actual
code (not just recollection): all 10 brief goals confirmed implemented on
both backend and frontend, with real server-side enforcement (not just
UI-hidden) for the goals where that matters most — the lifecycle state
machine and cross-role permission checks. 136 backend tests across 14 files,
consistently covering negative/permission-denied/edge cases alongside happy
paths (404-vs-403 on invisible projects, illegal transitions leaving state
untouched, bulk atomicity, archived-project freezes). One honest gap noted:
the append-only task-event timeline is immutable by application-code
discipline (no edit/delete route or function exists, and there's a test
proving no such route exists) rather than by a database-level constraint —
acceptable for this scope, but worth naming plainly if asked.

## What was cut / deferred

- Refresh-token revocation (documented trade-off).
- Rate limiting on login and invite-accept — known gap.
- Per-project task reference numbers.
- Multi-hop dependency cycle detection — only the direct A↔B case is caught
  (`services/tasks.py`); a longer cycle (A→B→C→A) is not detected.
