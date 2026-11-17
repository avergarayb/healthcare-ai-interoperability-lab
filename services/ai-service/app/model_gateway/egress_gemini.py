"""Per-execution Gemini consent. Absence leaves the gateway on the offline adapter.

An OpenAI consent is not this consent. The consent names one Gemini authorization
and can arm one send. It is not a process-wide switch.
"""
import threading

from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.gemini_configuration import ALLOWED_MODEL
from app.model_gateway.sdk_bridge import gemini_operational_reservation


PHRASE = (
    "CONFIRMO EGRESS-002 UNA SOLICITUD gemini gemini-3.5-flash-lite vacation-days-v1 "
    "DATOS SINTETICOS SIN REINTENTO"
)
DEPLOYMENT_ID = "gemini-sdk-a"
_OUTPUT_TOKENS = 256


class OperationalGeminiConsent:
    """One Gemini execution. The constructor is closed; use issue()."""

    def __init__(self):
        raise ProviderError("egress_blocked")

    def __repr__(self):
        return "OperationalGeminiConsent(closed)"

    def __reduce_ex__(self, protocol):
        raise TypeError("egress consent is not portable")

    @classmethod
    def issue(cls, mapping, *, authorization_id, deployment_id, organization_id, principal_id,
              resource_id, phrase, interactive, timeout_seconds=15, max_output_tokens=_OUTPUT_TOKENS,
              model_id=ALLOWED_MODEL, http_client=None):
        if interactive is not True or phrase != PHRASE:
            raise ProviderError("confirmation_required")
        if type(mapping) is not dict:
            raise ProviderError("credential_absent")
        credential = mapping.get("GEMINI_API_KEY")
        if type(credential) is not str or credential == "":
            raise ProviderError("credential_absent")
        if (deployment_id != DEPLOYMENT_ID or model_id != ALLOWED_MODEL
                or type(authorization_id) is not str or authorization_id == ""
                or type(organization_id) is not str or type(principal_id) is not str
                or type(resource_id) is not str or resource_id == ""):
            raise ProviderError("model_denied")
        if (timeout_seconds != 15 or max_output_tokens != _OUTPUT_TOKENS):
            raise ProviderError("not_configured")
        consent = object.__new__(cls)
        consent._credential = credential
        consent._authorization_id = authorization_id
        consent._deployment_id = deployment_id
        consent._organization_id = organization_id
        consent._principal_id = principal_id
        consent._resource_id = resource_id
        consent._model_id = model_id
        consent._http_client = http_client
        consent._used = False
        consent._requests = [0]
        consent._lock = threading.Lock()
        return consent

    @property
    def requests_sent(self):
        return self._requests[0]

    def matches(self, access, deployment, resource_id, budget_microusd, authorization_id):
        if (self._used is True or authorization_id != self._authorization_id
                or deployment.deployment_id != self._deployment_id
                or deployment.identity.provider_id != "gemini"
                or deployment.identity.model_id != self._model_id
                or deployment.egress_allowed is not False or deployment.endpoint is not None):
            raise ProviderError("egress_blocked")
        if access.organization_id != self._organization_id or access.principal_id != self._principal_id:
            raise ProviderError("scope_mismatch")
        if resource_id != self._resource_id:
            raise ProviderError("scope_mismatch")
        reservation = gemini_operational_reservation()
        if type(budget_microusd) is not int or isinstance(budget_microusd, bool):
            raise ProviderError("invalid_input")
        if budget_microusd < reservation or budget_microusd > 5_000_000:
            raise ProviderError("budget_exceeded")
        return True

    def claim(self, access, deployment, resource_id, authorization_id):
        with self._lock:
            self.matches(
                access, deployment, resource_id, gemini_operational_reservation(), authorization_id)
            self._used = True
            from app.enterprise_llm_providers.authorized_gemini_transport import SendRelease
            return SendRelease(self._requests)


def bind_gemini_consent(consent, access, deployment, resource_id, budget_microusd, authorization_id):
    """Check the Gemini consent before the ledger holds the permit."""
    if type(consent) is not OperationalGeminiConsent:
        raise ProviderError("egress_blocked")
    try:
        consent.matches(access, deployment, resource_id, budget_microusd, authorization_id)
    except ProviderError:
        raise
    except Exception:
        raise ProviderError("egress_blocked") from None


def arm_gemini_adapter(resolver_clock, consent, access, deployment, resource_id, authorization_id):
    """Build the one-shot adapter. The release is spent only inside send."""
    from app.enterprise_llm_providers.authorized_gemini_transport import OneShotGeminiTransport
    from app.enterprise_llm_providers.gemini_configuration import GeminiSettings
    from app.model_gateway.sdk_bridge import GeminiSdkBridge
    release = consent.claim(access, deployment, resource_id, authorization_id)
    transport = OneShotGeminiTransport(
        consent._credential, release, http_client=consent._http_client)
    settings = GeminiSettings(True, ALLOWED_MODEL, 15, _OUTPUT_TOKENS, 2048, 1_000, consent._credential)
    return GeminiSdkBridge(settings, transport, resolver_clock)
