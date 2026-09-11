# Architecture

The application is a separate React SPA and FastAPI API backed by PostgreSQL. The frontend is responsible for presentation and user interaction, while the backend owns authorization, business rules, task lifecycle validation, and database writes.

## Moving pieces

### React SPA

The frontend is a React + TypeScript single-page application built with Vite.

It handles:

- Login and invitation acceptance
- Project and team management
- Task list, filtering, sorting, bulk actions, and task details
- Dashboard and alerts
- Client-side form validation and UI state

The frontend communicates with the backend through HTTPS JSON API requests. Authenticated requests send the access token in the `Authorization: Bearer <token>` header.

The frontend does not decide whether an operation is actually allowed. It uses server-provided information such as `allowed_transitions` to make the UI reflect the current server rules, but the backend remains authoritative.

### FastAPI API

The backend is a stateless FastAPI application.

It is responsible for:

- Authentication and invitation acceptance
- Role-based authorization
- Project visibility and membership
- Task CRUD and assignment
- Task lifecycle/state-machine validation
- Dependency validation
- Immutable task history/timeline
- Dashboard aggregation
- Overdue alerts and dismissal
- Bulk operations and CSV export

The backend is organized into:

```text
app/
├── routers/       HTTP endpoints and request/response handling
├── services/      business and domain logic
├── schemas/       Pydantic request/response models
├── models.py      SQLAlchemy ORM models
├── deps.py        authentication/authorization dependencies
└── main.py        application setup and exception handling
```

Routers stay thin and delegate business rules to services. Services do not depend on FastAPI and raise typed service errors. The router owns the transaction boundary and commits after successful service operations.

### PostgreSQL

PostgreSQL is the system's source of truth.

It stores:

- Users and roles
- Invitations
- Projects and memberships
- Tasks
- Task assignments
- Task dependencies
- Task history/comments
- Alert dismissals

SQLAlchemy 2.0 provides the ORM layer and Alembic manages schema migrations.

The application uses real PostgreSQL for development and testing rather than relying on SQLite, because the implementation uses PostgreSQL-specific behavior such as savepoints, upserts, and database constraints.

## Where the pieces run

### Local development

```text
Browser
   │
   │ HTTP
   ▼
Vite React dev server
   │
   │ HTTPS/HTTP API requests
   ▼
FastAPI
   │
   │ SQLAlchemy
   ▼
PostgreSQL
```

PostgreSQL runs via Docker Compose; the FastAPI app runs locally against it through a Python virtual environment (`docker-compose.yml` also defines an `api` service for a fully-containerized option, but local development has run the API directly via `uvicorn`, not that service). The React application runs through the Vite development server.

### Production

```text
Browser → HTTPS → Vercel (React SPA) → HTTPS → Render (FastAPI) → TLS/SQL → Neon (PostgreSQL)
```

The frontend and backend are deployed separately. Environment variables provide deployment-specific configuration such as the API URL and database connection details.

## How a request moves through the system

A representative action is moving a task from `In Review` to `Done`.

```text
Browser
  │
  │ POST /api/tasks/{id}/transition
  │ { "to_status": "done" }
  │ Authorization: Bearer <access-token>
  ▼
FastAPI Router
  │
  ├── authenticate caller
  │
  └── resolve visible task
        │
        ▼
    Task Service
        │
        └── load dependencies
        │
        ▼
    Lifecycle Service
        │
        ├── verify project is active
        ├── validate allowed transition
        ├── verify no unfinished blockers
        └── update status/completed_at
        │
        ▼
    Event Service
        │
        └── append immutable STATUS_CHANGED event
        │
        ▼
    SQLAlchemy transaction
        │
        ▼
    PostgreSQL
        │
        ▼
    FastAPI response
        │
        └── task + recalculated allowed_transitions
              │
              ▼
           React UI
```

### End-to-end behavior

1. The user clicks Done in the React application.
2. React sends the transition request with the access token.
3. FastAPI authentication resolves the current user from the token.
4. The backend checks whether the user can see the task's project.
5. The task service loads the task's dependencies.
6. The lifecycle service checks that the project is not archived, then validates that the requested state transition is allowed.
7. The lifecycle service checks the task's dependencies. A task cannot become `Done` while a blocking dependency is unfinished.
8. If valid, the task status and `completed_at` are updated.
9. An immutable timeline event records the status change.
10. The router commits the transaction.
11. The API returns the updated task, including its currently allowed transitions.
12. React updates the UI from the server response.

If any validation fails, the service raises an appropriate error and the transaction is not committed.

## Server-side authorization

Authorization is enforced by the backend rather than by the frontend.

The JWT identifies the caller, but the database `users.role` is authoritative for authorization.

```text
JWT
 │
 └── sub → user ID
             │
             ▼
        users table
             │
             └── current role
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
       Manager             Member
```

Managers have portfolio-wide project visibility and can manage projects, membership, and task operations according to the API rules.

Members can only access projects they belong to. For project/task visibility failures, the API uses `404` rather than `403` so that an inaccessible project is not confirmed to exist.

The same visibility rules are reused by task queries, dashboard queries, and alerts rather than being independently reimplemented in each endpoint.

## Bulk operations

Bulk task actions use the same domain services as individual task operations. For example:

```text
POST /api/tasks/bulk
        │
        ▼
Bulk Service
        │
        ├── Task A → savepoint → transition service
        │                         └── success
        │
        ├── Task B → savepoint → transition service
        │                         └── validation error → rollback savepoint
        │
        └── Task C → savepoint → transition service
                                  └── success
        │
        ▼
Commit once
```

Each task is isolated with a savepoint. A failure for one task does not roll back successful changes for other tasks.

This also means bulk operations inherit the same lifecycle, assignment, permission, and archived-project rules as single-task operations instead of maintaining a second implementation of those rules.

## Important architectural invariants

Several rules are intentionally enforced in the service layer so they cannot be bypassed by using another endpoint:

- Archived projects freeze task work mutations.
- Only project members can be assigned to tasks.
- Task lifecycle transitions are validated server-side.
- Tasks cannot be marked `Done` while blocking dependencies remain unfinished.
- Timeline/history entries are immutable.
- Project visibility is centralized and reused by task, dashboard, and alert queries.
- Database role is authoritative over the JWT role claim.
- Bulk operations reuse the same domain services as individual operations.

## What I decided not to build

These were deliberately left out because they were either outside the brief, unnecessary for the take-home scope, or explicitly described as stretch work.

- **Open user registration** — no public sign-up. Managers control who joins via a one-time invitation; the employee sets their own password on accept.
- **Refresh-token revocation store** — refresh tokens are stateless and just expire; adding a server-side revocation list wasn't required for the assignment.
- **Task reference numbers** — no human-readable project/task numbers; UUIDs were sufficient and the brief didn't ask for them.
- **Multi-hop dependency cycle detection** — self- and immediate-reverse dependencies are blocked; full graph-based cycle detection across longer chains was left as stretch work.
- **Redis / background infrastructure** — everything is handled directly through the API and PostgreSQL; no extra runtime dependency was needed.

## Architecture principle

The main architectural choice was to keep the frontend relatively thin and make the backend authoritative:

```text
React
  ↓
FastAPI
  ↓
Domain services
  ↓
PostgreSQL
```

The UI can improve usability by hiding impossible actions, but it never becomes the source of truth for permissions or business rules. This makes the same rules apply consistently across individual actions, bulk operations, dashboard queries, and the deployed application.
