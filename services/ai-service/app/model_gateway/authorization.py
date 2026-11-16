"""Neutral authorization port. This module does not open a database."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, repr=False)
class DurableDecision:
    """ALLOW is a stored permission. It does not open egress or a live call."""

    allowed: bool
    reason: str
    authorization_id: str | None
    deployment_id: str | None
    provider_id: str | None
    model_id: str | None
    organization_id: str | None

    def __post_init__(self):
        if type(self.allowed) is not bool or self.allowed is not (self.reason == "accepted"):
            raise ValueError("closed decision")

    def __repr__(self):
        return "DurableDecision(closed)"


class DurableAuthorizationResolver:
    """Default resolver. It denies every request and is not an operational authority."""

    def resolve(self, access, authorization_id, deployment):
        return DurableDecision(False, "remote_not_authorized", None, None, None, None, None)
