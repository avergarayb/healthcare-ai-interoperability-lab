"""Provider-neutral contracts. Provider-specific fields stay inside adapters."""
from dataclasses import dataclass

from app.enterprise_llm_providers.errors import ProviderError


CAPABILITIES = frozenset({
    "text", "structured_output", "tool_calling", "streaming", "vision",
    "context_window", "token_accounting", "reasoning_control", "usage_report",
})


@dataclass(frozen=True, slots=True, repr=False)
class ModelIdentity:
    provider_id: str
    model_id: str

    def __repr__(self):
        return "ModelIdentity(closed)"


@dataclass(frozen=True, slots=True, repr=False)
class ModelDeployment:
    deployment_id: str
    identity: ModelIdentity
    execution_location: str
    capabilities: frozenset
    data_handling_policy: str
    reservation_microusd: int
    allowed_organizations: frozenset
    egress_allowed: bool = False
    endpoint: str | None = None

    def __repr__(self):
        return "ModelDeployment(closed)"


@dataclass(frozen=True, slots=True, repr=False)
class ModelCapabilities:
    supported: frozenset

    def allows(self, required):
        return set(required).issubset(self.supported)


@dataclass(frozen=True, slots=True, repr=False)
class ExecutionContext:
    organization_id: str
    principal_id: str
    resource_id: str
    purpose: str
    classification: str
    budget_microusd: int

    def __repr__(self):
        return "ExecutionContext(closed)"


@dataclass(frozen=True, slots=True, repr=False)
class ExecutionGrant:
    provider_id: str
    deployment_id: str
    organization_id: str
    principal_id: str
    resource_id: str
    purpose: str
    classification: str
    required_capabilities: tuple
    revision: int

    def __repr__(self):
        return "ExecutionGrant(closed)"


@dataclass(frozen=True, slots=True, repr=False)
class ModelRequest:
    use_case: str
    organization_id: str
    principal_id: str
    resource_id: str
    source_text: str

    def __repr__(self):
        return "ModelRequest(closed)"


@dataclass(frozen=True, slots=True, repr=False)
class UsageMetadata:
    input_tokens: int | None
    output_tokens: int | None

    def __repr__(self):
        return "UsageMetadata(closed)"


@dataclass(frozen=True, slots=True, repr=False)
class ModelResponse:
    deployment_id: str
    observation: dict | None
    usage: UsageMetadata
    estimated_microusd: int | None
    thoughts_tokens: int | None = None
    cost_exact: bool | None = None
    thoughts_inferred: bool | None = None
    tool_inferred: bool | None = None
    prompt_inferred: bool | None = None
    visible_inferred: bool | None = None

    def __repr__(self):
        return "ModelResponse(closed)"


@dataclass(frozen=True, slots=True, repr=False)
class ExecutionPolicy:
    max_invocations: int = 1
    allow_fallback: bool = False
    allow_egress: bool = False

    def __post_init__(self):
        if self.max_invocations != 1 or self.allow_fallback is not False or self.allow_egress is not False:
            raise ProviderError("policy_denied")


@dataclass(frozen=True, slots=True, repr=False)
class GatewayResult:
    """Public outcome. It carries no days, months, excerpt, or provider text."""

    accepted: bool
    reason: str
    deployment_id: str
    organization_id: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    reserved_microusd: int | None = None
    estimated_microusd: int | None = None
    thoughts_tokens: int | None = None
    cost_exact: bool | None = None
    thoughts_inferred: bool | None = None
    tool_inferred: bool | None = None
    prompt_inferred: bool | None = None
    visible_inferred: bool | None = None

    def __repr__(self):
        return "GatewayResult(closed)"
