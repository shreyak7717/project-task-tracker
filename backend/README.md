# Backend — Project & Task Tracker API

FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL.

## Local development

### Option A — Docker Compose (from repo root)

```bash
docker compose up --build
```

API on http://localhost:8000, docs on http://localhost:8000/docs.

### Option B — local venv

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements-dev.txt
cp .env.example .env          # then start Postgres (docker compose up db)
uvicorn app.main:app --reload
```

## Tests

```bash
cd backend
pytest
```

## Migrations

```bash
alembic revision --autogenerate -m "message"
alembic upgrade head
```
