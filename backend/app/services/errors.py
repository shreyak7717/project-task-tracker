"""Domain error types.

Each carries the HTTP status a router (or the global handler in app.main)
should translate it to. This keeps services free of FastAPI while still letting
them express "not found" vs "conflict" vs "forbidden".
"""

from __future__ import annotations


class ServiceError(Exception):
    status_code = 400

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class ValidationError(ServiceError):
    status_code = 400


class NotFoundError(ServiceError):
    status_code = 404


class PermissionDeniedError(ServiceError):
    status_code = 403


class ConflictError(ServiceError):
    status_code = 409
