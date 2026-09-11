# AI prompts

The prompts I actually used, in the order they mattered during development, grouped by what I was trying to achieve. I used AI as an interactive engineering partner: to plan the work, understand implementation choices, review edge cases, debug the deployed application, and revise decisions when testing exposed problems.

## Plan the project and divide the work

### Prompt

"Look at what the project is about and the 10 goals which need to be implemented and according to that suggest how should the sessions be divided with backend and frontend in separate sessions while also ensuring that the session progresses the project flow wise."

### What you got

The initial roadmap divided the roughly 12-hour project into six sessions:

1. Foundation + data model
2. Auth + RBAC
3. Projects + Tasks + lifecycle
4. Assignment, list/search, bulk, CSV
5. Frontend core
6. Dashboard, alerts, deploy, docs

It also recommended committing after meaningful steps and starting with the repository foundation.

### What you corrected

The original roadmap later proved too compressed around the frontend and backend completion. I deliberately changed the order to finish the backend first, moving dashboard and alerts ahead of the frontend. The later plan also expanded the work into additional sessions for frontend, deployment, seed data, and documentation. This was a planning correction based on the actual complexity of the implementation rather than blindly following the first AI-generated schedule.

## Build the project while understanding the code

### Prompt

"I wanna code dont just create file We will create file one by one so that I can review the work and tell the changes which need to be done."

### What you got

The implementation was changed into an incremental, file-by-file workflow. Each piece was explained, implemented, tested, and then committed before moving to the next coherent part.

### What you corrected

I kept questioning the implementation instead of accepting generated code as final. For example, I pushed back on unfamiliar concepts and what else could have been done here.

## Redesign account creation

### Prompt

"Changes to make to the Session 2 plan -
Replace the direct manager-created user accounts with a manager-invited account flow so no public self-registration. manager creates an invitation, not a user/password and the invitation contains email, invited_by, role=MEMBER, secure hashed one-time token, expiry, accepted_at, created_at all od the essential stuff. employee accepts the invitation and sets their own password."

### What you got

The initial plan proposed a manager endpoint that directly creates a user with a manager-chosen password.

### What you corrected

I changed this to a manager-invited flow: a manager issues a one-time, hashed, expiring invitation token, and the invitee sets their own name and password when accepting it. This keeps each person's credential with its actual owner instead of a manager knowing everyone's initial password, and only the token's hash is stored, so a database leak alone doesn't yield working invitations.

## Understand the authentication and JWT design

### Prompt

"Explain JWT claims: sub, role, iat, exp, type=access"

### What you got

During Session 2, I asked AI to explain the JWT claims used in the authentication implementation.

| Claim | Full name | Value | Purpose |
|---|---|---|---|
| `sub` | Subject | User UUID | Identifies which user the token belongs to. The backend uses it to load the user from the database. |
| `role` | Custom claim | `manager` or `member` | Convenience for role-aware UI. It is not trusted for authorization because the backend reads the user's current role from the database. |
| `iat` | Issued At | UTC timestamp | Records when the token was created. |
| `exp` | Expiration | Timestamp | Determines when the token expires. Access tokens are short-lived while refresh tokens have a longer lifetime. |
| `type` | Custom claim | `access` or `refresh` | Distinguishes access tokens from refresh tokens so they cannot be used interchangeably. |

`sub`, `iat`, and `exp` are registered JWT claims. `role` and `type` are custom claims defined by the application.

The JWT payload is Base64-encoded, not encrypted, so its contents can be read by anyone who has the token. The token is signed using the JWT secret, which prevents the payload from being modified without invalidating the signature.

Most importantly, the `role` claim is not the source of truth for authorization. The backend uses the user's role from the database. This means that if a user's role changes after a token was issued, the database value determines what they are allowed to do.

### What you corrected

I required the database `User.role` to remain authoritative instead of trusting the JWT `role` claim, so a demotion or deactivation takes effect immediately rather than waiting for the token to expire.

## Make Session 4 rules precise before implementation

### Prompt

I gave four clarifications before starting Session 4:

"Make these clarifications to Session 4 before implementation:

1. `set_assignees()` must validate all requested assignees are members of the task's project before making any changes; for a single-task replacement, invalid input rejects the entire operation atomically with no partial assignment changes.
2. Clarify permissions: the caller may be a project member (or manager, who has project-wide access), but every target assignee must be a member of that task's project.
3. Verify Session 1 database indexes support the server-side Goal 6 query patterns, especially task/project filtering and `task_assignees(user_id, task_id)`; add an Alembic migration only if required indexes are missing.
4. Keep bulk operations per-task atomic using savepoints and reuse the existing task/lifecycle/assignment services rather than duplicating business rules.
5. Keep everything else in Session 4 unchanged and aligned with Goals 5–7 of the company brief."

### What you got

The implementation plan was tightened around atomic assignment replacement, separate caller/target permission checks, the composite assignee index, and reuse of existing business rules inside bulk operations.

### What you corrected

I explicitly checked the permissions table because the distinction between "who may perform the action" and "who may be assigned" could easily be conflated. The final rule became: a project member or manager may manage assignments, but every assignee must belong to that task's project.

## Make dashboard and alert calculations consistent

### Prompt

Before Session 5 I gave four correctness clarifications:

1. All dashboard and alert date calculations must consistently use UTC. Establish one clear UTC date reference for the request instead of relying on PostgreSQL `CURRENT_DATE` unless the database/session timezone is explicitly configured to UTC.
2. Use explicit rolling 7-day bucket boundaries anchored to the current UTC date. Do not use `date_trunc('week')`, because the dashboard definition is rolling 7-day periods rather than calendar weeks.
3. Preserve M:N assignee semantics. An open task assigned to multiple users contributes once to each assigned user's count. Open unassigned tasks contribute to the `user: null` bucket.
4. Make alert dismissal concurrency-safe and idempotent using an upsert. Store the due date at dismissal time so that an alert resurfaces if the task's due date changes.

### What you got

The dashboard and alert plan used a single UTC date reference, explicit rolling 7-day buckets, M:N assignee counts, and a concurrency-safe dismissal upsert.

### What you corrected

I challenged whether all four details were actually relevant before implementation. The resulting design treated them as correctness requirements rather than optional implementation details. The dashboard and alerts were then completed on the backend before building the frontend against the finished API.

## Catch a wrong initial design for archived projects

### Prompt

"I think we should also do this Add a guard: block create_task / transition_task / assign when project.is_archived, returning a 409."

### What you got

The existing archive behavior only hid projects from normal views. The proposed change added a shared service-layer guard that blocks task work mutations while archived and allows the manager to restore the project.

### What you corrected

This became an explicit reversal of the original archive behavior. I decided that archived work should actually be frozen rather than merely hidden. Comments and dependency changes remained available for historical/reference purposes. The guard was placed in the service layer so normal and bulk operations use the same rule.

## Catch another inconsistency after the archive change

### Prompt

"I want these for tasks as well so people dont get confused"

### What you got

Task lists were given an `include_archived` option and rows could identify tasks belonging to archived projects.

### What you corrected

I noticed that the Projects page already made archived state explicit, while task lists still made archived tasks look normal. I asked for the same concept to be exposed for tasks so the UI would explain why those tasks were frozen instead of making the user discover the restriction by clicking an action.

## Find a dashboard inconsistency through live testing

### Prompt

"but why is it still showing on dashboard then so archived is not working correctly here"

### What you got

The dashboard was identified as a separate aggregate path that had not inherited the task-list archive filtering.

### What you corrected

I changed the dashboard scope so archived-project tasks were excluded from its aggregates as well. This kept the dashboard's definition of current work consistent with the task-list behavior.

## Fix alert scope for different roles

### Prompt

"now alice is a member, the alert which is being shown is of bob so it shouldnt be shown to alice right? so members will get alerts according to their task only whereas a manager can see all alerts."

### What you got

Testing showed that the alert list exposed overdue tasks across visible projects even when the member was not assigned to them, while dismissal itself was already restricted to assigned tasks.

### What you corrected

I changed the final behavior so members see only overdue alerts for tasks assigned to them, while managers retain the portfolio-wide alert view. This was documented as a partial reversal of the earlier alert-scope decision.

## Keep the implementation plan truthful

### Prompt

"rewrite plan.md since we had changes and it went stale in mock_doc folder"

### What you got

The plan was rewritten to reflect the actual session order, implementation time, completed backend work, frontend work, deployment, testing discoveries, and late archive changes.

### What you corrected

Instead of preserving the original AI-generated roadmap as if it had been followed exactly, I updated it to distinguish the planned order from the actual order. This included documenting why dashboard/alerts moved before the frontend and recording the changes discovered during live deployment testing.

## Debug the deployed application rather than assuming the local implementation was enough

### Prompt

Several prompts were driven by live deployment behavior, including:

- "why didnt we put the values which we have in .env file?"
- "why is it not automatically sending an email with invite why?"
- "it opened that page which asks for your name and password for just 1 sec then just opened the manager dashboard why?"

### What you got

These led to explanations and debugging around deployment environment variables, the development-only invitation URL behavior, and the invitation acceptance flow.

### What you corrected

I tested the actual deployed frontend/backend instead of assuming that local success meant the deployment was correct. Deployment-specific issues were fixed and then re-tested against the live application.

## Fix frontend issues found by the build and UI

### Prompt

I used screenshots and short debugging prompts when the deployed UI exposed problems, for example:

"The dialog box is spilling when we are inviting a member through email see"

and later a Vercel build showing a TypeScript TS6133 error.

### What you got

The UI issues were traced to the affected dialog/layout and the TypeScript build failure was identified from the deployment output.

### What you corrected

I iterated on the UI rather than treating the initial frontend implementation as finished. The dialog overflow was fixed, the build error was addressed, and the frontend was redeployed and tested again.

## Summary

The most useful AI interactions were not simply "generate this file" prompts. The important pattern was:

plan → implement → question the design → test → find an inconsistency → correct it → update the documentation.

The AI's first answer was not always treated as authoritative. The initial six-session roadmap was later changed, the original archive semantics were reversed after testing, and the member alert scope was revised after testing different users. These corrections were kept as part of the engineering history rather than hidden.
