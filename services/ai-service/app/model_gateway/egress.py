"""Per-execution OpenAI consent. Absence leaves the gateway on the offline adapter.

A durable ALLOW is not this consent. The consent names one authorization and
can arm one send. It is not a process-wide switch.
"""
import threading

from app.enterprise_llm_providers.configuration import ALLOWED_MODEL
from app.enterprise_llm_providers.errors import ProviderError
from app.model_gateway.sdk_bridge import openai_reservation


PHRASE = (
    "CONFIRMO EGRESS-001 UNA SOLICITUD openai gpt-6-luna vacation-days-v1 "
    "DATOS SINTETICOS SIN REINTENTO"
)
DEPLOYMENT_ID = "openai-sdk-a"
_OUTPUT_MIN = 16
_OUTPUT_MAX = 256


class OperationalEgressConsent:
    """One execution. The constructor is closed; use issue()."""

    def __init__(self):
        raise ProviderError("egress_blocked")

    def __repr__(self):
        return "OperationalEgressConsent(closed)"

    def __reduce_ex__(self, protocol):
        raise TypeError("egress consent is not portable")

    @classmethod
    def issue(cls, mapping, *, authorization_id, deployment_id, organization_id, principal_id,
              resource_id, phrase, interactive, timeout_seconds=15, max_output_tokens=16,
              model_id=ALLOWED_MODEL, http_client=None):
        if interactive is not True or phrase != PHRASE:
            raise ProviderError("confirmation_required")
        if type(mapping) is not dict:
            raise ProviderError("credential_absent")
        credential = mapping.get("OPENAI_API_KEY")
        if type(credential) is not str or credential == "":
            raise ProviderError("credential_absent")
        if (deployment_id != DEPLOYMENT_ID or model_id != ALLOWED_MODEL
                or type(authorization_id) is not str or authorization_id == ""
                or type(organization_id) is not str or type(principal_id) is not str
                or type(resource_id) is not str or resource_id == ""):
            raise ProviderError("model_denied")
        if (type(timeout_seconds) not in (int, float) or isinstance(timeout_seconds, bool)
                or not 0 < float(timeout_seconds) <= 60
                or type(max_output_tokens) is not int
                or not _OUTPUT_MIN <= max_output_tokens <= _OUTPUT_MAX):
            raise ProviderError("not_configured")
        consent = object.__new__(cls)
        consent._credential = credential
        consent._authorization_id = authorization_id
        consent._deployment_id = deployment_id
        consent._organization_id = organization_id
        consent._principal_id = principal_id
        consent._resource_id = resource_id
        consent._timeout_seconds = float(timeout_seconds)
        consent._max_output_tokens = max_output_tokens
        consent._model_id = model_id
        consent._http_client = http_client
        consent._used = False
        consent._requests = [0]
        consent._lock = threading.Lock()
        return consent

    @property
    def requests_sent(self):
        return self._requests[0]

    def matches(self, access, deployment, resource_id, budget_microusd):
        if (self._used is True or deployment.deployment_id != self._deployment_id
                or deployment.identity.provider_id != "openai"
                or deployment.identity.model_id != self._model_id
                or deployment.egress_allowed is not False or deployment.endpoint is not None):
            raise ProviderError("egress_blocked")
        if access.organization_id != self._organization_id or access.principal_id != self._principal_id:
            raise ProviderError("scope_mismatch")
        if resource_id != self._resource_id:
            raise ProviderError("scope_mismatch")
        reservation = openai_reservation()
        if type(budget_microusd) is not int or isinstance(budget_microusd, bool):
            raise ProviderError("invalid_input")
        if budget_microusd < reservation or budget_microusd > 5_000_000:
            raise ProviderError("budget_exceeded")
        return True

    def claim(self, access, deployment, resource_id):
        with self._lock:
            self.matches(access, deployment, resource_id, openai_reservation())
            self._used = True
            from app.enterprise_llm_providers.authorized_transport import SendRelease
            return SendRelease(self._requests)


def bind_consent(consent, access, deployment, resource_id, budget_microusd):
    """Check the consent before the ledger holds the permit."""
    if type(consent) is not OperationalEgressConsent:
        raise ProviderError("egress_blocked")
    try:
        consent.matches(access, deployment, resource_id, budget_microusd)
    except ProviderError:
        raise
    except Exception:
        raise ProviderError("egress_blocked") from None


def arm_openai_adapter(resolver_clock, consent, access, deployment, resource_id):
    """Build the one-shot adapter. The release is spent only inside send."""
    from app.enterprise_llm_providers.authorized_transport import OneShotOpenAITransport
    from app.enterprise_llm_providers.configuration import ProviderSettings
    from app.model_gateway.sdk_bridge import OpenAISdkBridge
    release = consent.claim(access, deployment, resource_id)
    transport = OneShotOpenAITransport(
        consent._credential, release, http_client=consent._http_client,
        timeout_seconds=consent._timeout_seconds)
    settings = ProviderSettings(
        True, ALLOWED_MODEL, consent._timeout_seconds, consent._max_output_tokens,
        2048, 5_000_000, 5_000_000, consent._credential)
    return OpenAISdkBridge(settings, transport, resolver_clock)
