from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import alerts, auth, dashboard, projects, task_list, tasks, users
from app.services.errors import ServiceError

app = FastAPI(title="Project & Task Tracker API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Content-Disposition isn't on the CORS-safelisted response headers, so a
    # cross-origin fetch() can't read the CSV filename without this.
    expose_headers=["Content-Disposition"],
)


@app.exception_handler(ServiceError)
async def _service_error_handler(_: Request, exc: ServiceError) -> JSONResponse:
    """Translate domain errors raised by the service layer into JSON responses."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/api/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(projects.router)
app.include_router(task_list.router)  # before tasks.router: literal paths win
app.include_router(tasks.router)
app.include_router(dashboard.router)
app.include_router(alerts.router)
