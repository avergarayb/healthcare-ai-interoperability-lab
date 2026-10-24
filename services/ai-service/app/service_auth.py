"""Laboratory service-to-service authentication. Fail-closed. Do not log the token."""

from __future__ import annotations

import hashlib
import hmac

from fastapi import Request

from app.config import Settings


def authenticate(request: Request, settings: Settings) -> bool:
    configured = settings.model_boundary_service_token
    presented_values = request.headers.getlist("X-Service-Token")
    if not isinstance(configured, str) or not configured or configured.isspace():
        return False
    if len(presented_values) != 1:
        return False
    presented = presented_values[0]
    if not presented or presented.isspace():
        return False
    return hmac.compare_digest(
        hashlib.sha256(configured.encode("utf-8")).digest(),
        hashlib.sha256(presented.encode("utf-8")).digest(),
    )
