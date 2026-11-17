"""One jurisdiction consent. Another operation's consent cannot arm this send."""
import threading

from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.gemini_configuration import ALLOWED_MODEL
from app.model_gateway.sdk_bridge import gemini_operational_reservation

from .policy import DEPLOYMENT_ID
from .profile import OPERATION_ID


PHRASE = (
    "CONFIRMO MULTI-COUNTRY-001 UNA SOLICITUD INTERCEPTADA gemini gemini-3.5-flash-lite "
    "jurisdiction-lab-summary-v1 DATOS SINTETICOS SIN REINTENTO REVISION HUMANA"
)


class OperationalJurisdictionConsent:
    """One jurisdiction summary. The constructor is closed; use issue()."""

    def __init__(self):
        raise ProviderError("egress_blocked")

    def __repr__(self):
        return "OperationalJurisdictionConsent(closed)"

    def __reduce_ex__(self, protocol):
        raise TypeError("jurisdiction consent is not portable")

    @classmethod
    def issue(cls, mapping, *, profile, principal_id, phrase, interactive, timeout_seconds=15,
              max_output_tokens=256, model_id=ALLOWED_MODEL, http_client=None):
        if interactive is not True or phrase != PHRASE:
            raise ProviderError("confirmation_required")
        if type(mapping) is not dict:
            raise ProviderError("credential_absent")
        credential = mapping.get("GEMINI_API_KEY")
        if type(credential) is not str or credential == "":
            raise ProviderError("credential_absent")
        if http_client is None:
            raise ProviderError("provider_send_blocked")
        if (model_id != ALLOWED_MODEL or type(principal_id) is not str or principal_id == ""
                or profile is None or profile.organization_id == ""):
            raise ProviderError("model_denied")
        if timeout_seconds != 15 or max_output_tokens != 256:
            raise ProviderError("not_configured")
        consent = object.__new__(cls)
        consent._credential = credential
        consent._authorization_id = profile.authorization_id
        consent._deployment_id = DEPLOYMENT_ID
        consent._organization_id = profile.organization_id
        consent._principal_id = principal_id
        consent._resource_id = profile.patient_value
        consent._policy_ref = profile.policy_ref
        consent._model_id = model_id
        consent._operation_id = OPERATION_ID
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
                or self._operation_id != OPERATION_ID
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


def bind_jurisdiction_consent(consent, access, deployment, resource_id, budget_microusd, authorization_id):
    if type(consent) is not OperationalJurisdictionConsent:
        raise ProviderError("egress_blocked")
    consent.matches(access, deployment, resource_id, budget_microusd, authorization_id)
