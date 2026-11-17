"""Durable deployment permission. An active row does not open egress or C03."""
from dataclasses import dataclass
from datetime import datetime


POLICY_REF = "model-gateway-policy-v1"
OPERATION_ID = "vacation-days-v1"
CLINICAL_OPERATION_ID = "lab-result-summary-v1"
CLINICAL_POLICY_REF = "lab-result-summary-policy-v1"
CAPABILITY = "structured_output+usage_report"
SCOPES = {
    ("openai-sdk-a", "openai", "gpt-6-luna"),
    ("openai-offline-a", "openai", "gpt-6-luna"),
    ("gemini-sdk-a", "gemini", "gemini-3.5-flash-lite"),
    ("gemini-offline-a", "gemini", "gemini-3.5-flash-lite"),
}
# Closed catalog reservations, in integer micro-USD. A stored ceiling below
# the reservation cannot be active. The maximum matches the laboratory cap.
RESERVATION_MICROUSD = {
    "openai-offline-a": 191,
    "gemini-offline-a": 470,
    "openai-sdk-a": 303,
    "gemini-sdk-a": 977,
}
BUDGET_CEILING_MAX_MICROUSD = 5_000_000
REVOCATION_REASONS = frozenset({"operator_revoked", "scope_withdrawn"})
DECISION_REASONS = frozenset({
    "accepted", "not_granted", "scope_mismatch", "not_yet_effective", "authorization_expired",
    "revoked", "wrong_deployment", "wrong_provider", "wrong_model", "operation_denied",
    "revision_conflict", "invalid_input", "storage_unavailable", "authority_unverifiable",
    "budget_exceeded", "replay_denied",
})


@dataclass(frozen=True, slots=True, repr=False)
class RemoteAuthorization:
    authorization_id: str
    organization_id: str
    deployment_id: str
    provider_id: str
    model_id: str
    valid_from: datetime
    expires_at: datetime
    operation_id: str = OPERATION_ID
    capability: str = CAPABILITY
    policy_ref: str = POLICY_REF
    policy_version: int = 1
    principal_id: str | None = None
    resource_id: str | None = None
    budget_ceiling_microusd: int | None = None

    def __repr__(self):
        return "RemoteAuthorization(closed)"


@dataclass(frozen=True, slots=True, repr=False)
class RemoteAuthorizationDecision:
    """ALLOW here is a stored permission. It is not a live call and not a C03 connection."""

    allowed: bool
    reason: str
    authorization_id: str | None
    egress_allowed: bool = False
    live_authorized: bool = False
    c03_connected: bool = False

    def __post_init__(self):
        if (self.egress_allowed is not False or self.live_authorized is not False
                or self.c03_connected is not False or self.reason not in DECISION_REASONS
                or type(self.allowed) is not bool or self.allowed is not (self.reason == "accepted")):
            raise ValueError("closed decision")

    def __repr__(self):
        return "RemoteAuthorizationDecision(closed)"


def classify(row, now_us, query):
    """Compare one stored row with the exact requested scope. Missing row is denial."""
    if row is None:
        return "not_granted"
    if query.deployment_id != row["deployment_id"]:
        return "wrong_deployment"
    if query.provider_id != row["provider_id"]:
        return "wrong_provider"
    if query.model_id != row["model_id"]:
        return "wrong_model"
    if query.operation_id != row["operation_id"]:
        return "operation_denied"
    if row["status"] == "revoked":
        return "revoked"
    if now_us < row["valid_from_us"]:
        return "not_yet_effective"
    if now_us >= row["expires_at_us"]:
        return "authorization_expired"
    if row["status"] != "active":
        return "not_granted"
    if query.principal_id is not None and query.principal_id != row["principal_id"]:
        return "scope_mismatch"
    if query.resource_id is not None and query.resource_id != row["resource_id"]:
        return "scope_mismatch"
    return "accepted"
