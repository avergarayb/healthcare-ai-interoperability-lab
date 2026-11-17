"""Closed jurisdiction policy. A real provider send stays blocked."""
from app.enterprise_llm_providers.errors import ProviderError

from .profile import OPERATION_ID


DEPLOYMENT_ID = "gemini-sdk-a"


def request_real_provider_send():
    """The demonstration transport is intercepted. This method does not open a provider."""
    raise ProviderError("provider_send_blocked")
