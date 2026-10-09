"""Synthetic development principal copied onto one business operation.

This is not a verified clinical identity. It does not carry a session token,
a token hash, a secret, or clinical data.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass


DEVELOPMENT_AUTHENTICATOR_V1 = "DEVELOPMENT_AUTHENTICATOR_V1"
REVIEW_CASE_CLOSED = "review_case_closed"
COORDINATION_REQUEST_CREATED = "coordination_request_created"
_PRINCIPAL_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


@dataclass(frozen=True)
class DevelopmentPrincipalSnapshot:
    """Server-copied development principal. Not a verified clinician."""

    principal_id: str
    authenticator_id: str
    session_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.principal_id, str) or _PRINCIPAL_ID.fullmatch(self.principal_id) is None:
            raise ValueError("development principal id is invalid")
        if self.authenticator_id != DEVELOPMENT_AUTHENTICATOR_V1:
            raise ValueError("development authenticator id is invalid")
        if not isinstance(self.session_id, str):
            raise ValueError("development session id is invalid")
        try:
            parsed = uuid.UUID(self.session_id)
        except (ValueError, TypeError):
            raise ValueError("development session id is invalid") from None
        if str(parsed) != self.session_id:
            raise ValueError("development session id is invalid")


@dataclass(frozen=True)
class StoredDevelopmentAttribution:
    """Attribution fields safe to render. Session id stays in the review row only."""

    operation: str
    principal_id: str
    occurred_at: str


def validate_development_principal_snapshot(
    snapshot: DevelopmentPrincipalSnapshot,
) -> DevelopmentPrincipalSnapshot:
    if not isinstance(snapshot, DevelopmentPrincipalSnapshot):
        raise ValueError("development principal snapshot is invalid")
    DevelopmentPrincipalSnapshot(
        snapshot.principal_id,
        snapshot.authenticator_id,
        snapshot.session_id,
    )
    return snapshot
