"""Domain logic.

Rules of this layer:
- No FastAPI imports. Functions take a SQLAlchemy ``Session`` and plain
  arguments, and raise ``app.services.errors.ServiceError`` subclasses.
- Services ``flush`` but never ``commit`` — the calling router owns the
  transaction boundary, so one request can compose several service calls.
"""
