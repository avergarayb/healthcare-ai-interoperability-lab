"""Laboratory service-to-service authentication. Fail-closed. Do not log the token."""

from __future__ import annotations

from fastapi import Request

from app.config import Settings


def authenticate(request: Request, settings: Settings) -> bool:
    presented = request.headers.get("X-Service-Token")
    configured = settings.model_boundary_service_token
    if not configured:
        return False
    if presented is None or presented == "":
        return False
    return presented == configured
